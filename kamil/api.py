"""Server endpoints for Kamil Energy's simplified 2-step buying/selling flows.

Both flows follow the same shape:

    Step 1  -> create & submit the Order (Purchase Order / Sales Order)
    Step 2  -> create & submit the Invoice from that Order with ``update_stock = 1``
               so goods are received/delivered directly (no Purchase Receipt /
               Delivery Note required).

Everything here is metadata-aware: transport custom fields are only touched when
they actually exist on the target DocType, so the same code works on a
stripped-down site and on the full Kamil Energy production setup.
"""

import json

import frappe
from frappe import _
from frappe.utils import flt, nowdate

# Transport custom fields captured on the order and carried onto the invoice.
# Applied only when present on the DocType (see ``_apply_transport``).
TRANSPORT_FIELDS = (
	"custom_vehicle",
	"custom_license_plate",
	"custom_trailer_plate",
	"custom_transporter",
	"custom_driver",
	"custom_driver_name",
	"custom_driver_id",
	"custom_driver_contact",
)

def _load(value):
	if isinstance(value, str):
		return json.loads(value) if value else {}
	return value or {}


def _apply_transport(doc, transport):
	transport = _load(transport)
	if not transport:
		return
	for fieldname in TRANSPORT_FIELDS:
		if doc.meta.has_field(fieldname) and transport.get(fieldname) not in (None, ""):
			doc.set(fieldname, transport.get(fieldname))


def _copy_transport(source, target):
	for fieldname in TRANSPORT_FIELDS:
		if source.meta.has_field(fieldname) and target.meta.has_field(fieldname):
			value = source.get(fieldname)
			if value not in (None, ""):
				target.set(fieldname, value)


def _add_items(doc, items, warehouse_field, date_field, fallback_warehouse, fallback_date):
	items = items or []
	for item in items:
		item_code = (item.get("item_code") or "").strip()
		if not item_code:
			continue
		row = doc.append("items", {})
		row.item_code = item_code
		row.qty = flt(item.get("qty"))
		if item.get("uom"):
			row.uom = item.get("uom")
		if item.get("rate") not in (None, ""):
			row.rate = flt(item.get("rate"))
		row.set(warehouse_field, item.get("warehouse") or fallback_warehouse)
		row.set(date_field, item.get(date_field) or fallback_date)
	if not doc.get("items"):
		frappe.throw(_("Add at least one item before continuing."))


# ---------------------------------------------------------------------------
# Purchase flow
# ---------------------------------------------------------------------------


@frappe.whitelist()
def create_purchase_order(order: dict | str) -> dict:
	"""Step 1 (Purchase): create and submit a Purchase Order."""
	order = _load(order)

	doc = frappe.new_doc("Purchase Order")
	doc.supplier = order.get("supplier")
	doc.company = order.get("company")
	doc.transaction_date = order.get("transaction_date") or nowdate()
	doc.schedule_date = order.get("schedule_date") or doc.transaction_date
	if order.get("set_warehouse") and doc.meta.has_field("set_warehouse"):
		doc.set_warehouse = order.get("set_warehouse")

	_apply_transport(doc, order.get("transport"))
	_add_items(
		doc,
		order.get("items"),
		warehouse_field="warehouse",
		date_field="schedule_date",
		fallback_warehouse=order.get("set_warehouse"),
		fallback_date=doc.schedule_date,
	)
	doc.insert()
	doc.submit()

	return _order_summary(doc)


@frappe.whitelist()
def create_purchase_invoice(purchase_order: str, receipt: dict | str | None = None) -> dict:
	"""Step 2 (Purchase): create and submit a stock-updating Purchase Invoice."""
	from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_invoice

	receipt = _load(receipt)
	po = frappe.get_doc("Purchase Order", purchase_order)

	inv = make_purchase_invoice(purchase_order)
	inv.update_stock = 1

	default_warehouse = receipt.get("set_warehouse") or po.get("set_warehouse")
	if default_warehouse and inv.meta.has_field("set_warehouse"):
		inv.set_warehouse = default_warehouse
	for row in inv.items:
		if not row.warehouse:
			row.warehouse = default_warehouse

	if receipt.get("posting_date"):
		inv.set_posting_time = 1
		inv.posting_date = receipt.get("posting_date")
	for fieldname in ("bill_no", "bill_date", "custom_supplier_invoice", "supplier_delivery_note"):
		if receipt.get(fieldname) and inv.meta.has_field(fieldname):
			inv.set(fieldname, receipt.get(fieldname))

	_copy_transport(po, inv)

	inv.insert()
	inv.submit()

	return _invoice_summary(inv)


# ---------------------------------------------------------------------------
# Sales flow
# ---------------------------------------------------------------------------


@frappe.whitelist()
def create_sales_order(order: dict | str) -> dict:
	"""Step 1 (Sales): create and submit a Sales Order."""
	order = _load(order)

	doc = frappe.new_doc("Sales Order")
	doc.customer = order.get("customer")
	doc.company = order.get("company")
	doc.transaction_date = order.get("transaction_date") or nowdate()
	doc.delivery_date = order.get("delivery_date") or doc.transaction_date
	if order.get("set_warehouse") and doc.meta.has_field("set_warehouse"):
		doc.set_warehouse = order.get("set_warehouse")

	_apply_transport(doc, order.get("transport"))
	_add_items(
		doc,
		order.get("items"),
		warehouse_field="warehouse",
		date_field="delivery_date",
		fallback_warehouse=order.get("set_warehouse"),
		fallback_date=doc.delivery_date,
	)
	doc.insert()
	doc.submit()

	return _order_summary(doc)


@frappe.whitelist()
def create_sales_invoice(sales_order: str, delivery: dict | str | None = None) -> dict:
	"""Step 2 (Sales): create and submit a stock-updating Sales Invoice."""
	from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

	delivery = _load(delivery)
	so = frappe.get_doc("Sales Order", sales_order)

	inv = make_sales_invoice(sales_order)
	inv.update_stock = 1

	default_warehouse = delivery.get("set_warehouse") or so.get("set_warehouse")
	if default_warehouse and inv.meta.has_field("set_warehouse"):
		inv.set_warehouse = default_warehouse
	for row in inv.items:
		if not row.warehouse:
			row.warehouse = default_warehouse

	if delivery.get("posting_date"):
		inv.set_posting_time = 1
		inv.posting_date = delivery.get("posting_date")
	if delivery.get("po_no") and inv.meta.has_field("po_no"):
		inv.po_no = delivery.get("po_no")

	_copy_transport(so, inv)

	inv.insert()
	inv.submit()

	return _invoice_summary(inv)


# ---------------------------------------------------------------------------
# Helpers shared by both flows
# ---------------------------------------------------------------------------


def _order_summary(doc):
	return {
		"name": doc.name,
		"doctype": doc.doctype,
		"currency": doc.currency,
		"grand_total": doc.grand_total,
		"items": [
			{
				"item_code": row.item_code,
				"item_name": row.item_name,
				"qty": row.qty,
				"uom": row.uom,
				"rate": row.rate,
				"amount": row.amount,
				"warehouse": row.warehouse,
			}
			for row in doc.items
		],
	}


def _invoice_summary(inv):
	return {
		"name": inv.name,
		"doctype": inv.doctype,
		"currency": inv.currency,
		"grand_total": inv.grand_total,
		"outstanding_amount": inv.outstanding_amount,
	}


# ---------------------------------------------------------------------------
# Kamil Hub dashboard
# ---------------------------------------------------------------------------


def _can_read(doctype):
	return frappe.has_permission(doctype, "read")


def _sum_where(doctype, sum_field, where, params):
	rows = frappe.db.sql(f"select coalesce(sum({sum_field}), 0) from `tab{doctype}` where {where}", params)
	return flt(rows[0][0]) if rows else 0.0


def _company_clause(company):
	return (" and company = %(company)s" if company else ""), {"company": company}


def _invoice_total_mtd(doctype, company):
	if not _can_read(doctype):
		return None
	clause, params = _company_clause(company)
	params["start"] = frappe.utils.get_first_day(nowdate())
	return _sum_where(
		doctype,
		"base_grand_total",
		"docstatus = 1 and is_return = 0 and posting_date >= %(start)s" + clause,
		params,
	)


def _invoice_outstanding(doctype, company):
	if not _can_read(doctype):
		return None
	clause, params = _company_clause(company)
	return _sum_where(doctype, "outstanding_amount", "docstatus = 1 and outstanding_amount > 0" + clause, params)


def _monthly_invoice_totals(doctype, company, start):
	if not _can_read(doctype):
		return {}
	clause, params = _company_clause(company)
	params["start"] = start
	rows = frappe.db.sql(
		f"""select date_format(posting_date, '%%Y-%%m') as ym, sum(base_grand_total) as total
		from `tab{doctype}`
		where docstatus = 1 and is_return = 0 and posting_date >= %(start)s{clause}
		group by ym""",
		params,
		as_dict=True,
	)
	return {r.ym: flt(r.total) for r in rows}


def _count(doctype, filters):
	if not _can_read(doctype):
		return None
	try:
		return frappe.db.count(doctype, filters)
	except Exception:
		return None


def _recent_invoices(doctype, party_field, company):
	if not _can_read(doctype):
		return []
	filters = {"company": company} if company else {}
	return frappe.get_list(
		doctype,
		filters=filters,
		fields=["name", f"{party_field} as party", "status", "grand_total", "currency", "posting_date", "docstatus"],
		order_by="modified desc",
		limit_page_length=6,
	)


@frappe.whitelist()
def get_hub_data(company: str | None = None) -> dict:
	"""Aggregate KPIs, monthly totals, shortcut counts and recent documents
	for the Kamil Hub page. Everything is permission-gated per DocType;
	blocks the user cannot read come back as None/empty and the client
	hides them."""
	companies = frappe.get_list("Company", pluck="name", order_by="name")
	if company and company not in companies:
		company = None
	if not company:
		default = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
			"Global Defaults", "default_company"
		)
		company = default if default in companies else (companies[0] if len(companies) == 1 else None)

	currency = (
		frappe.get_cached_value("Company", company, "default_currency")
		if company
		else frappe.db.get_single_value("Global Defaults", "default_currency")
	)

	# last 6 months, oldest first
	first_of_month = frappe.utils.get_first_day(nowdate())
	months = []
	for offset in range(5, -1, -1):
		d = frappe.utils.add_months(first_of_month, -offset)
		months.append({"key": d.strftime("%Y-%m"), "label": frappe.utils.formatdate(d, "MMM")})

	purchases_by_month = _monthly_invoice_totals("Purchase Invoice", company, months[0]["key"] + "-01")
	sales_by_month = _monthly_invoice_totals("Sales Invoice", company, months[0]["key"] + "-01")

	return {
		"company": company,
		"companies": companies,
		"currency": currency,
		"kpis": {
			"mtd_purchases": _invoice_total_mtd("Purchase Invoice", company),
			"mtd_sales": _invoice_total_mtd("Sales Invoice", company),
			"payables": _invoice_outstanding("Purchase Invoice", company),
			"receivables": _invoice_outstanding("Sales Invoice", company),
		},
		"monthly": [
			{
				"label": m["label"],
				"purchases": purchases_by_month.get(m["key"], 0.0),
				"sales": sales_by_month.get(m["key"], 0.0),
			}
			for m in months
		],
		"counts": {
			"open_po": _count(
				"Purchase Order",
				{"docstatus": 1, "status": ["not in", ["Completed", "Closed"]], **({"company": company} if company else {})},
			),
			"unpaid_pinv": _count(
				"Purchase Invoice",
				{"docstatus": 1, "outstanding_amount": [">", 0], **({"company": company} if company else {})},
			),
			"supplier": _count("Supplier", {"disabled": 0}),
			"open_so": _count(
				"Sales Order",
				{"docstatus": 1, "status": ["not in", ["Completed", "Closed"]], **({"company": company} if company else {})},
			),
			"unpaid_sinv": _count(
				"Sales Invoice",
				{"docstatus": 1, "outstanding_amount": [">", 0], **({"company": company} if company else {})},
			),
			"customer": _count("Customer", {"disabled": 0}),
			"item": _count("Item", {"disabled": 0}),
			"vehicle": _count("Vehicle", {}),
			"warehouse": _count("Warehouse", {"is_group": 0, **({"company": company} if company else {})}),
			"payment_entry": _count(
				"Payment Entry", {"docstatus": 1, **({"company": company} if company else {})}
			),
		},
		"recent_purchases": _recent_invoices("Purchase Invoice", "supplier", company),
		"recent_sales": _recent_invoices("Sales Invoice", "customer", company),
	}
