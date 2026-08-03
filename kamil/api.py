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

import datetime
import decimal
import json
import re

import frappe
from frappe import _
from frappe.model.workflow import get_workflow_name
from frappe.utils import cint, flt, nowdate

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


# What a Vehicle contributes to a transport document, as target_field: vehicle_field.
# Mirrors the desk Client Script on Sales Invoice -- that script only runs in the
# desk form, so anything created through the app has to fill these itself.
_VEHICLE_MAP = {
	"custom_license_plate": "license_plate",
	"custom_trailer_plate": "custom_trailer_plate",
	"custom_driver": "custom_driver",
	"custom_driver_name": "full_name",
	"custom_driver_id": "custom_driver_id",
	"custom_driver_contact": "custom_driver_contact",
	"custom_transporter": "custom_transporter",
}


def _fill_sales_team(doc) -> None:
	"""Take the sales team from the customer when the document has none.

	The salesperson belongs to the customer — whoever owns the account earns on it —
	so it does not have to be picked on every order. A team entered on the document
	itself always wins.
	"""
	if not doc.meta.has_field("sales_team") or doc.get("sales_team"):
		return
	customer = doc.get("customer")
	if not customer:
		return

	for row in frappe.get_all(
		"Sales Team",
		filters={"parent": customer, "parenttype": "Customer"},
		fields=["sales_person", "allocated_percentage", "commission_rate", "incentives"],
	):
		doc.append("sales_team", row)


def _fill_taxes(doc) -> None:
	"""Load the tax table when a document was created without one.

	Taxes come from the customer's or company's default template, and each line's own
	Item Tax Template then applies on top — which is how an invoice ends up taxed the
	way the items say it should be, rather than not at all.
	"""
	if not doc.meta.has_field("taxes") or doc.get("taxes"):
		return
	if doc.get("taxes_and_charges"):
		return

	party_field = "customer" if doc.meta.has_field("customer") else "supplier"
	template_doctype = "Sales Taxes and Charges Template" if party_field == "customer" else "Purchase Taxes and Charges Template"
	if not frappe.db.exists("DocType", template_doctype):
		return

	template = None
	party = doc.get(party_field)
	if party:
		# A tax category on the party picks a specific template.
		category = frappe.db.get_value(party_field.capitalize(), party, "tax_category")
		if category:
			template = frappe.db.get_value(
				template_doctype, {"company": doc.get("company"), "tax_category": category, "disabled": 0}, "name"
			)
	if not template:
		template = frappe.db.get_value(
			template_doctype, {"company": doc.get("company"), "is_default": 1, "disabled": 0}, "name"
		)
	if not template:
		return

	doc.taxes_and_charges = template
	for row in frappe.get_all(
		"Sales Taxes and Charges" if party_field == "customer" else "Purchase Taxes and Charges",
		filters={"parent": template},
		fields=["*"],
		order_by="idx asc",
	):
		for field in ("name", "owner", "creation", "modified", "modified_by", "parent", "parentfield", "parenttype", "idx", "docstatus"):
			row.pop(field, None)
		doc.append("taxes", row)


def _fill_from_vehicle(doc):
	"""Populate plate/driver/transporter (and compartments) from `custom_vehicle`.

	Every write is guarded on the field existing on both sides, so this is a no-op on
	a site that has not got the transport customisation installed.
	"""
	vehicle_name = doc.get("custom_vehicle")
	if not vehicle_name or not frappe.db.exists("Vehicle", vehicle_name):
		return

	meta = frappe.get_meta(doc.doctype)
	vehicle = frappe.get_doc("Vehicle", vehicle_name)

	for target, source in _VEHICLE_MAP.items():
		if meta.has_field(target) and not doc.get(target):
			value = vehicle.get(source)
			if value:
				doc.set(target, value)

	# The vehicle's own warehouse is where its stock sits.
	if meta.has_field("set_warehouse") and not doc.get("set_warehouse"):
		warehouse = vehicle.get("custom_default_warehouse")
		if warehouse:
			doc.set("set_warehouse", warehouse)

	# Compartments come across as rows, matching what the desk script builds.
	if meta.has_field("custom_vehicle_compartments") and not doc.get("custom_vehicle_compartments"):
		for row in vehicle.get("custom_vehicle_compartments") or []:
			doc.append("custom_vehicle_compartments", {"name1": row.get("name1"), "qty": row.get("qty")})


@frappe.whitelist()
def get_vehicle_details(vehicle: str) -> dict:
	"""Everything a transport document takes from a Vehicle, for the create form."""
	if not vehicle or not frappe.db.exists("Vehicle", vehicle) or not _can_read("Vehicle"):
		return {}

	doc = frappe.get_doc("Vehicle", vehicle)
	out = {target: doc.get(source) for target, source in _VEHICLE_MAP.items()}
	out["set_warehouse"] = doc.get("custom_default_warehouse")
	out["compartments"] = [
		{"name1": r.get("name1"), "qty": r.get("qty")} for r in (doc.get("custom_vehicle_compartments") or [])
	]
	return out


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


def _invoice_total_since(doctype, company, start):
	if not _can_read(doctype):
		return None
	clause, params = _company_clause(company)
	params["start"] = start
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
			"today_sales": _invoice_total_since("Sales Invoice", company, nowdate()),
			"today_purchases": _invoice_total_since("Purchase Invoice", company, nowdate()),
			"ytd_sales": _invoice_total_since("Sales Invoice", company, frappe.utils.get_year_start(nowdate())),
			"ytd_purchases": _invoice_total_since("Purchase Invoice", company, frappe.utils.get_year_start(nowdate())),
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


# ---------------------------------------------------------------------------
# Quick-create helpers for the Kamil frontend (modals referencing existing docs)
# ---------------------------------------------------------------------------


@frappe.whitelist()
def list_open_invoices(invoice_type: str):
	"""Outstanding invoices for the 'Record Payment' modal."""
	dt = "Sales Invoice" if invoice_type == "Sales" else "Purchase Invoice"
	party_field = "customer_name" if dt == "Sales Invoice" else "supplier_name"
	rows = frappe.get_list(
		dt,
		filters={"docstatus": 1, "outstanding_amount": [">", 0]},
		fields=["name", f"{party_field} as party", "outstanding_amount", "currency"],
		order_by="outstanding_amount desc",
		limit_page_length=50,
	)
	return [
		{
			"value": r.name,
			"label": f"{r.name} · {r.party or ''} · {frappe.utils.fmt_money(r.outstanding_amount, currency=r.currency)}",
			"outstanding": r.outstanding_amount,
			"currency": r.currency,
		}
		for r in rows
	]


@frappe.whitelist()
def list_open_orders(order_type: str):
	"""Un-billed orders for the 'Invoice from Order' modal."""
	dt = "Sales Order" if order_type == "Sales" else "Purchase Order"
	party_field = "customer_name" if dt == "Sales Order" else "supplier_name"
	rows = frappe.get_list(
		dt,
		filters={"docstatus": 1, "status": ["not in", ["Closed", "Completed"]], "per_billed": ["<", 100]},
		fields=["name", f"{party_field} as party", "grand_total", "currency"],
		order_by="transaction_date desc",
		limit_page_length=50,
	)
	return [
		{
			"value": r.name,
			"label": f"{r.name} · {r.party or ''} · {frappe.utils.fmt_money(r.grand_total, currency=r.currency)}",
		}
		for r in rows
	]


@frappe.whitelist()
def get_exchange_rate(from_currency: str, to_currency: str, date: str | None = None) -> dict:
	"""Today's rate between two currencies, so the request form can suggest one."""
	if not from_currency or not to_currency or from_currency == to_currency:
		return {"rate": 1.0, "source": "same currency"}

	try:
		from erpnext.setup.utils import get_exchange_rate as _rate

		rate = flt(_rate(from_currency, to_currency, date or nowdate(), args="for_buying"))
		return {"rate": rate or None, "source": "Currency Exchange" if rate else "not found"}
	except Exception:
		return {"rate": None, "source": "not found"}


@frappe.whitelist()
def list_modes_of_payment(company: str | None = None) -> list:
	"""Modes of payment, each with the account the money actually moves through.

	The account's currency is what the payer is billed in, and it is often not the
	currency on the invoice — a USD invoice paid from a KES account. The label carries
	it so nobody has to guess which pot the money leaves.
	"""
	company = _resolve_company(company)
	rows = frappe.get_list("Mode of Payment", filters={"enabled": 1}, pluck="name", order_by="name")

	out = []
	for name in rows:
		account = frappe.db.get_value(
			"Mode of Payment Account", {"parent": name, "company": company}, "default_account"
		)
		currency = frappe.db.get_value("Account", account, "account_currency") if account else None
		out.append(
			{
				"value": name,
				"label": f"{name} · {currency}" if currency else name,
				"account": account,
				"currency": currency,
			}
		)
	return out


@frappe.whitelist()
def make_invoice_from_order(order_type: str, order_name: str):
	"""Create a DRAFT invoice mapped from an existing order and return its name."""
	if order_type == "Sales":
		from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

		doc = make_sales_invoice(order_name)
	else:
		from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_invoice

		doc = make_purchase_invoice(order_name)
	doc.insert()
	return {"name": doc.name, "doctype": doc.doctype}


@frappe.whitelist()
def get_payment_entry_draft(
	invoice_type: str,
	invoice_name: str,
	amount: float | str | None = None,
	mode_of_payment: str | None = None,
) -> dict:
	"""Map an invoice onto a Payment Entry and return it **unsaved**.

	Same idea as `get_next_document_draft`: the app opens the payment form on these
	values so the user sees what they are about to post — the bank account, the
	allocation, the reference row — instead of a draft appearing silently behind them.
	"""
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	dt = "Sales Invoice" if invoice_type == "Sales" else "Purchase Invoice"
	frappe.has_permission(dt, "read", doc=invoice_name, throw=True)
	frappe.has_permission("Payment Entry", "create", throw=True)

	account = None
	if mode_of_payment:
		from kamil.payment_flow import _mode_of_payment_account

		company = frappe.db.get_value(dt, invoice_name, "company")
		account = _mode_of_payment_account(mode_of_payment, company)

	pe = get_payment_entry(dt, invoice_name, bank_account=account)
	if mode_of_payment:
		pe.mode_of_payment = mode_of_payment
	if amount:
		amount = flt(amount)
		pe.paid_amount = amount
		pe.received_amount = amount
		if pe.references:
			pe.references[0].allocated_amount = amount

	values = {}
	for field, value in pe.as_dict().items():
		if value in (None, "") or field.startswith("_"):
			continue
		if isinstance(value, list):
			rows = [
				{
					k: _scalar(v)
					for k, v in _plain_row(row).items()
					if v not in (None, "") and not k.startswith("_") and k not in _CHILD_META_FIELDS
				}
				for row in value
			]
			if rows:
				values[field] = rows
		else:
			scalar = _scalar(value)
			if scalar is not None:
				values[field] = scalar

	for field in _DOC_META_FIELDS:
		values.pop(field, None)

	return {"doctype": "Payment Entry", "values": values}


@frappe.whitelist()
def record_payment(
	invoice_type: str,
	invoice_name: str,
	amount: float | str | None = None,
	mode_of_payment: str | None = None,
	reference_no: str | None = None,
	reference_date: str | None = None,
):
	"""Create a DRAFT Payment Entry against an existing invoice and return its name.

	The mode of payment picks the account the money moves through — passed to
	``get_payment_entry`` as the bank account so ERPNext derives the currencies itself.
	A bank transaction also needs a reference number and date, which ERPNext refuses to
	save without; the date falls back to today when only a number is given.
	"""
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	dt = "Sales Invoice" if invoice_type == "Sales" else "Purchase Invoice"

	account = None
	if mode_of_payment:
		from kamil.payment_flow import _mode_of_payment_account

		company = frappe.db.get_value(dt, invoice_name, "company")
		account = _mode_of_payment_account(mode_of_payment, company)

	pe = get_payment_entry(dt, invoice_name, bank_account=account)
	if mode_of_payment:
		pe.mode_of_payment = mode_of_payment
	if amount:
		amount = flt(amount)
		pe.paid_amount = amount
		pe.received_amount = amount
		if pe.references:
			pe.references[0].allocated_amount = amount

	if reference_no:
		pe.reference_no = reference_no
		pe.reference_date = reference_date or nowdate()

	pe.insert()
	return {
		"name": pe.name,
		"doctype": pe.doctype,
		"paid_amount": flt(pe.paid_amount),
		"account": pe.paid_to if dt == "Sales Invoice" else pe.paid_from,
	}


@frappe.whitelist()
def search_link(doctype: str, txt: str = "", filters: str | dict | None = None):
	"""Link-field search for the in-app create modals."""
	txt = txt or ""
	try:
		filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	except Exception:
		filters = {}
	if not isinstance(filters, dict):
		filters = {}
	meta = frappe.get_meta(doctype)

	# A disabled record is disabled for a reason — offering it in a picker only leads to
	# a document nobody can submit. Skipped where the caller asked for something
	# explicit about the flag, so "show me the disabled ones" still works.
	if meta.has_field("disabled") and "disabled" not in filters:
		filters["disabled"] = 0
	if meta.has_field("enabled") and "enabled" not in filters:
		filters["enabled"] = 1

	title_field = meta.title_field if meta.title_field and meta.title_field != "name" else None
	or_filters = [["name", "like", f"%{txt}%"]]
	if title_field:
		or_filters.append([title_field, "like", f"%{txt}%"])
	fields = ["name"] + ([title_field] if title_field else [])
	rows = frappe.get_list(
		doctype, filters=filters, or_filters=or_filters, fields=fields,
		limit_page_length=15, order_by="modified desc",
	)
	out = []
	for r in rows:
		label = r.name
		if title_field and r.get(title_field) and r.get(title_field) != r.name:
			label = f"{r.name} · {r.get(title_field)}"
		out.append({"value": r.name, "label": label})
	return out


# Fieldtypes a small in-line "create new" form cannot sensibly render.
_QUICK_ENTRY_SKIP = (
	"Section Break", "Column Break", "Tab Break", "HTML", "Table", "Table MultiSelect",
	"Button", "Image", "Fold", "Heading", "Attach", "Attach Image", "Signature",
	"Geolocation", "Barcode", "Code", "Markdown Editor", "Text Editor", "HTML Editor",
	"Password", "Read Only", "Rating", "Duration", "Icon", "Color",
)
# Attach fields are renderable (the forms upload the file), so they are not skipped.
_QUICK_ENTRY_SKIP = tuple(f for f in _QUICK_ENTRY_SKIP if f not in ("Attach", "Attach Image"))

# Mandatory fields ERPNext fills in itself when a document is built. Asking for these
# in a create form would be noise — and getting them wrong is worse than leaving them.
_AUTOFILLED_FIELDS = {
	"naming_series", "company", "posting_date", "posting_time", "transaction_date", "due_date",
	"currency", "conversion_rate", "selling_price_list", "buying_price_list", "price_list_currency",
	"plc_conversion_rate", "debit_to", "credit_to", "party_account_currency", "status",
	"letter_head", "language", "territory", "customer_group", "supplier_group", "company_address",
	"against_income_account", "is_opening", "docstatus", "title", "customer_name", "supplier_name",
	"base_grand_total", "grand_total", "total", "net_total", "base_net_total", "rounded_total",
	"schedule_date", "set_posting_time", "update_stock", "apply_discount_on",
}

# App-facing fieldtype for each Frappe fieldtype the create forms can render.
_FORM_FIELDTYPES = {
	"Data": "data", "Select": "select", "Link": "link", "Dynamic Link": "data",
	"Date": "date", "Datetime": "date", "Check": "check", "Currency": "currency",
	"Float": "float", "Int": "float", "Percent": "float", "Small Text": "textarea",
	"Long Text": "textarea", "Text": "textarea", "Attach": "attach", "Attach Image": "attach",
	"Phone": "data",
}


@frappe.whitelist()
def get_missing_mandatory_fields(doctype: str, known: str | list | None = None) -> list:
	"""Mandatory fields a create form does not already ask for.

	Sites add their own required custom fields — a bill of lading, a vehicle, a
	commission — and a document cannot be submitted without them. Rather than hard-code
	each site's customisations, the form asks the doctype what else it needs and renders
	that alongside the fields the app declares itself.
	"""
	if not doctype or not frappe.db.exists("DocType", doctype):
		return []

	if isinstance(known, str):
		try:
			known = frappe.parse_json(known)
		except Exception:
			known = [k.strip() for k in known.split(",") if k.strip()]
	known = set(known or [])

	out = []
	for df in frappe.get_meta(doctype).fields:
		if not df.reqd or df.hidden or df.read_only:
			continue
		if df.fieldname in known or df.fieldname in _AUTOFILLED_FIELDS:
			continue
		fieldtype = _FORM_FIELDTYPES.get(df.fieldtype)
		if not fieldtype:
			continue
		# A field with a default needs no prompting — the document arrives with it.
		if df.default and df.fieldtype not in ("Select",):
			continue
		out.append(
			{
				"fieldname": df.fieldname,
				"label": _(df.label or df.fieldname),
				"fieldtype": fieldtype,
				"options": df.options or "",
				"reqd": 1,
				"description": df.description or "",
				"selectOptions": [
					{"label": o.strip() or "—", "value": o.strip()}
					for o in (df.options or "").split("\n")
					if df.fieldtype == "Select"
				],
			}
		)
	return out
_QUICK_ENTRY_MAX_FIELDS = 12


@frappe.whitelist()
def get_quick_entry(doctype: str) -> dict:
	"""The few fields needed to create a record of `doctype` from a link field.

	Same idea as the desk's Quick Entry: everything mandatory, plus anything the
	doctype explicitly marks for quick entry. `can_create` is what the UI gates the
	"Create new" option on — the insert itself is still permission-checked by Frappe.
	"""
	out = {"doctype": doctype, "label": _(doctype), "can_create": False, "fields": [], "prompt_name": False}
	if not doctype or not frappe.db.exists("DocType", doctype):
		return out

	out["can_create"] = bool(frappe.has_permission(doctype, "create"))
	if not out["can_create"]:
		return out

	meta = frappe.get_meta(doctype)
	out["prompt_name"] = (meta.autoname or "").lower() == "prompt"
	out["title_field"] = meta.title_field or None

	fields = []
	for df in meta.fields:
		if df.fieldtype in _QUICK_ENTRY_SKIP or df.hidden or df.read_only:
			continue
		if not (df.reqd or df.allow_in_quick_entry):
			continue
		if df.fieldname in ("naming_series",) and df.default:
			continue
		fields.append(
			{
				"fieldname": df.fieldname,
				"label": _(df.label or df.fieldname),
				"fieldtype": df.fieldtype,
				"options": df.options or "",
				"reqd": cint(df.reqd),
				"default": df.default or "",
				# Select options travel as a list so the UI can render them directly.
				"select_options": [
					{"label": o.strip(), "value": o.strip()}
					for o in (df.options or "").split("\n")
					if df.fieldtype == "Select" and o.strip()
				],
			}
		)

	out["fields"] = fields[:_QUICK_ENTRY_MAX_FIELDS]
	return out


@frappe.whitelist()
def get_form_field_meta(doctype: str, fieldnames: str | list | None = None) -> dict:
	"""Metadata for the fields a create/edit form wants to show.

	The forms are declared in the frontend, but some of the fields they ask for are
	site customisations that may not exist everywhere. This reports which ones are
	really on the doctype — the form drops the rest — and hands back each Select's
	options from the site itself, so a customised status list stays correct.
	"""
	out = {}
	if not doctype or not frappe.db.exists("DocType", doctype):
		return out

	if isinstance(fieldnames, str):
		try:
			fieldnames = frappe.parse_json(fieldnames)
		except Exception:
			fieldnames = [f.strip() for f in fieldnames.split(",") if f.strip()]
	if not isinstance(fieldnames, list):
		return out

	meta = frappe.get_meta(doctype)
	for fieldname in fieldnames:
		if not isinstance(fieldname, str):
			continue
		df = meta.get_field(fieldname)
		if not df or df.hidden:
			continue
		out[fieldname] = {
			"label": _(df.label or fieldname),
			"fieldtype": df.fieldtype,
			"options": df.options or "",
			"reqd": cint(df.reqd),
			"read_only": cint(df.read_only),
			"description": df.description or "",
			"select_options": [
				{"label": o.strip() or "—", "value": o.strip()}
				for o in (df.options or "").split("\n")
				if df.fieldtype == "Select"
			],
		}
	return out


@frappe.whitelist()
def create_document(doctype: str, values: str | dict | None = None):
	"""Insert a draft document (incl. child tables) from the create modal."""
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	values["doctype"] = doctype
	meta = frappe.get_meta(doctype)
	if not values.get("company") and meta.has_field("company"):
		values["company"] = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
			"Global Defaults", "default_company"
		)
	doc = frappe.get_doc(values)
	_fill_from_vehicle(doc)
	_fill_sales_team(doc)
	if "taxes" not in values:
		_fill_taxes(doc)
	# No Delivery Notes or Purchase Receipts in this flow, so an invoice carries the
	# stock movement itself. Only defaulted — a caller that passed update_stock keeps it.
	if "update_stock" not in values:
		_stock_updating_invoice(doc)
	doc.insert()
	return {"name": doc.name, "doctype": doc.doctype}


@frappe.whitelist()
def update_document(doctype: str, name: str, values: str | dict | None = None) -> dict:
	"""Save edits to an existing document from the in-app editor.

	Only draft documents are editable here. A submitted document has ledger entries
	behind it, so it must be amended or cancelled rather than quietly rewritten — and
	`doc.save()` would refuse most of those changes anyway.
	"""
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	if not isinstance(values, dict):
		frappe.throw(_("Invalid values."))

	doc = frappe.get_doc(doctype, name)
	doc.check_permission("write")

	if doc.docstatus == 1:
		frappe.throw(_("{0} is submitted. Amend it instead of editing.").format(name))
	if doc.docstatus == 2:
		frappe.throw(_("{0} is cancelled and can no longer be edited.").format(name))

	meta = frappe.get_meta(doctype)
	for field, value in values.items():
		# Never let the payload rewrite identity or workflow state.
		if field in ("name", "doctype", "docstatus", "owner", "creation", "workflow_state"):
			continue
		if meta.has_field(field):
			doc.set(field, value)

	_fill_from_vehicle(doc)
	doc.save()

	return {"name": doc.name, "doctype": doc.doctype}


# Contact and address details do not live on Customer — ERPNext keeps them in their
# own doctypes and links back. The create form still asks for them in one place, so
# these arrive prefixed and are split back out here.
_CONTACT_FIELDS = ("contact_first_name", "contact_last_name", "contact_mobile", "contact_email")
_ADDRESS_FIELDS = ("address_line1", "address_line2", "address_city", "address_country")


def _create_party_contact(party_type: str, party: str, values: dict) -> str | None:
	"""Contact for a new customer or supplier, linked back and set as its primary."""
	first = (values.get("contact_first_name") or "").strip()
	last = (values.get("contact_last_name") or "").strip()
	mobile = (values.get("contact_mobile") or "").strip()
	email = (values.get("contact_email") or "").strip()
	if not (first or last or mobile or email):
		return None

	contact = frappe.get_doc(
		{
			"doctype": "Contact",
			"first_name": first or party,
			"last_name": last or None,
			"mobile_no": mobile or None,
			"links": [{"link_doctype": party_type, "link_name": party}],
		}
	)
	if email:
		contact.append("email_ids", {"email_id": email, "is_primary": 1})
	if mobile:
		contact.append("phone_nos", {"phone": mobile, "is_primary_mobile_no": 1})
	contact.insert(ignore_permissions=True)

	primary_field = "customer_primary_contact" if party_type == "Customer" else "supplier_primary_contact"
	updates = {"mobile_no": mobile or None, "email_id": email or None}
	if frappe.get_meta(party_type).has_field(primary_field):
		updates[primary_field] = contact.name
	frappe.db.set_value(party_type, party, updates, update_modified=False)
	return contact.name


def _create_party_address(party_type: str, party: str, values: dict) -> str | None:
	"""Physical address for a new customer or supplier, linked back and set as primary."""
	line1 = (values.get("address_line1") or "").strip()
	city = (values.get("address_city") or "").strip()
	if not (line1 or city):
		return None

	address = frappe.get_doc(
		{
			"doctype": "Address",
			"address_title": party,
			"address_type": "Billing",
			"address_line1": line1 or city,
			"address_line2": (values.get("address_line2") or "").strip() or None,
			"city": city or None,
			"country": (values.get("address_country") or "").strip() or None,
			"is_primary_address": 1,
			"is_shipping_address": 1,
			"links": [{"link_doctype": party_type, "link_name": party}],
		}
	)
	address.insert(ignore_permissions=True)

	primary_field = "customer_primary_address" if party_type == "Customer" else "supplier_primary_address"
	if frappe.get_meta(party_type).has_field(primary_field):
		frappe.db.set_value(party_type, party, primary_field, address.name, update_modified=False)
	return address.name


def _create_party(party_type: str, values: str | dict | None) -> dict:
	"""Create a customer or supplier together with its contact and address.

	The form collects the whole picture — identity, statutory details, KYC documents,
	contact and address — but ERPNext spreads that across three doctypes. The party is
	inserted first so the other two can link to it; if either of them fails the party
	is still there, and the failure is reported rather than silently swallowed.
	"""
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	if not isinstance(values, dict):
		frappe.throw(_("Invalid details."))

	extras = {k: values.pop(k, None) for k in _CONTACT_FIELDS + _ADDRESS_FIELDS}

	values["doctype"] = party_type
	party = frappe.get_doc(values)
	party.insert()

	out = {"name": party.name, "doctype": party_type}
	for label, builder in (("contact", _create_party_contact), ("address", _create_party_address)):
		try:
			out[label] = builder(party_type, party.name, extras)
		except Exception as e:
			frappe.log_error(frappe.get_traceback(), f"Kamil: {party_type} {label} failed")
			out[f"{label}_error"] = str(e)

	return out


@frappe.whitelist()
def create_customer(values: str | dict | None = None) -> dict:
	"""Create a customer with its contact and address in one step."""
	return _create_party("Customer", values)


@frappe.whitelist()
def create_supplier(values: str | dict | None = None) -> dict:
	"""Create a supplier with its contact and address in one step."""
	return _create_party("Supplier", values)


@frappe.whitelist()
def get_create_defaults() -> dict:
	"""Preloaded defaults for the create modals (company, default warehouse).

	`Company.default_warehouse` does not exist in this ERPNext version, so the
	warehouse falls back to Stock Settings and finally to any non-group warehouse
	of the company. Every lookup is guarded so this never breaks the modals.
	"""
	company = None
	warehouse = None
	try:
		company = _resolve_company(None)
	except Exception:
		company = None

	try:
		default_wh = frappe.db.get_single_value("Stock Settings", "default_warehouse")
		if default_wh and (
			not company or frappe.db.get_value("Warehouse", default_wh, "company") == company
		):
			warehouse = default_wh
		if not warehouse and company:
			warehouse = frappe.db.get_value(
				"Warehouse", {"company": company, "is_group": 0}, "name", order_by="creation asc"
			)
	except Exception:
		warehouse = None

	return {"company": company, "warehouse": warehouse, "currency": _currency_for(company)}


@frappe.whitelist()
def submit_document(doctype: str, name: str) -> dict:
	"""Submit a draft document from the in-app viewer."""
	doc = frappe.get_doc(doctype, name)
	if get_workflow_name(doc.doctype):
		frappe.throw(
			_("{0} is driven by a workflow — use its approval actions instead of submitting.").format(_(doctype))
		)
	doc.submit()
	return {"name": doc.name, "docstatus": doc.docstatus}


@frappe.whitelist()
def get_doc_actions(doctype: str, name: str) -> dict:
	"""Which actions the in-app viewer may offer for a document.

	When an active workflow owns the doctype, the plain Submit button must not be
	shown at all — the document may only move through the workflow's transitions,
	and a direct submit would side-step the approvals it exists to enforce.
	"""
	out = {
		"docstatus": 0,
		"is_submittable": False,
		"can_submit": False,
		"can_cancel": False,
		"workflow": None,
		"workflow_state": None,
		"transitions": [],
	}
	if not doctype or not name or not frappe.db.exists("DocType", doctype):
		return out

	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	meta = frappe.get_meta(doctype)
	out["docstatus"] = cint(doc.docstatus)
	out["is_submittable"] = bool(meta.is_submittable)

	workflow = get_workflow_name(doctype)
	if workflow:
		from frappe.model.workflow import get_transitions

		state_field = frappe.db.get_value("Workflow", workflow, "workflow_state_field")
		out["workflow"] = workflow
		out["workflow_state"] = doc.get(state_field) if state_field else None
		try:
			out["transitions"] = [
				{"action": t.get("action"), "next_state": t.get("next_state")}
				for t in (get_transitions(doc) or [])
			]
		except Exception:
			# No state set yet, or the user holds none of the transition roles.
			out["transitions"] = []
		return out

	out["can_submit"] = bool(
		meta.is_submittable and cint(doc.docstatus) == 0 and frappe.has_permission(doctype, "submit", doc=doc)
	)
	out["can_cancel"] = bool(
		meta.is_submittable and cint(doc.docstatus) == 1 and frappe.has_permission(doctype, "cancel", doc=doc)
	)
	return out


@frappe.whitelist()
def apply_workflow_action(doctype: str, name: str, action: str) -> dict:
	"""Move a document along its workflow (Approve / Reject / …).

	Frappe checks the transition's role and self-approval rules itself, so this only
	has to make sure the caller may read the document in the first place.
	"""
	from frappe.model.workflow import apply_workflow

	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")

	workflow = get_workflow_name(doctype)
	if not workflow:
		frappe.throw(_("{0} has no active workflow.").format(_(doctype)))

	updated = apply_workflow(doc, action)
	state_field = frappe.db.get_value("Workflow", workflow, "workflow_state_field")
	return {
		"name": updated.name,
		"docstatus": cint(updated.docstatus),
		"workflow_state": updated.get(state_field) if state_field else None,
	}


@frappe.whitelist()
def send_document_whatsapp(
	doctype: str,
	name: str,
	phone_number: str | None = None,
	message: str | None = None,
	sender: str | None = None,
	print_format: str | None = None,
) -> dict:
	"""Send a document's PDF to its party via WhatsApp.

	The transport lives in ``kamil.whatsapp``: it wakes the gateway before sending and
	retries on the timeouts a sleeping gateway produces. See that module for why the
	integration app's own sender is not used directly.
	"""
	from kamil.whatsapp import send_document

	return send_document(
		doctype,
		name,
		phone_number=phone_number or None,
		message=message or None,
		sender=sender or None,
		print_format=print_format or None,
	)


@frappe.whitelist()
def warm_whatsapp() -> dict:
	"""Ping the WhatsApp gateway so it is awake before the user presses Send."""
	from kamil.whatsapp import warm_gateway

	return warm_gateway()


@frappe.whitelist()
def list_whatsapp_senders() -> list:
	"""WhatsApp sender numbers available to the current user (for the sender picker)."""
	try:
		from whatsapp_integration.api.whatsapp.whatsapp import get_whatsapp_senders
	except ImportError:
		return []

	rows = get_whatsapp_senders() or []
	return [{"label": r.get("label") or r.get("value"), "value": r.get("value")} for r in rows]


@frappe.whitelist()
def resolve_document_phone(doctype: str, name: str) -> str | None:
	"""Best-effort phone for a document's party (WhatsApp prefill).

	Order: the integration's own resolver -> phone fields on the document ->
	the party master's mobile/phone -> the party's linked Contact.
	"""
	try:
		from whatsapp_integration.service.utils import resolve_phone_number

		num = resolve_phone_number(doctype, name)
		if num:
			return num
	except Exception:
		pass

	try:
		doc = frappe.get_doc(doctype, name)

		for field in ("contact_mobile", "mobile_no", "contact_phone", "phone"):
			if doc.get(field):
				return doc.get(field)

		party_type = party = None
		if doc.get("customer"):
			party_type, party = "Customer", doc.get("customer")
		elif doc.get("supplier"):
			party_type, party = "Supplier", doc.get("supplier")
		elif doc.get("party_type") and doc.get("party"):
			party_type, party = doc.get("party_type"), doc.get("party")
		elif doc.get("quotation_to") and doc.get("party_name"):
			party_type, party = doc.get("quotation_to"), doc.get("party_name")

		if not (party_type and party):
			return None

		party_meta = frappe.get_meta(party_type)
		for field in ("mobile_no", "phone"):
			if party_meta.has_field(field):
				value = frappe.db.get_value(party_type, party, field)
				if value:
					return value

		contacts = frappe.get_all(
			"Dynamic Link",
			filters={"link_doctype": party_type, "link_name": party, "parenttype": "Contact"},
			pluck="parent",
		)
		for contact in contacts:
			row = frappe.db.get_value("Contact", contact, ["mobile_no", "phone"], as_dict=True)
			if row and (row.mobile_no or row.phone):
				return row.mobile_no or row.phone
	except Exception:
		pass

	return None


@frappe.whitelist()
def get_print_formats(doctype: str) -> list:
	"""Print formats available for a doctype (Standard first)."""
	if not frappe.db.exists("DocType", doctype):
		return []
	names = frappe.get_all(
		"Print Format", filters={"doc_type": doctype, "disabled": 0}, pluck="name", order_by="name"
	)
	default = frappe.db.get_value("Property Setter", {"doc_type": doctype, "property": "default_print_format"}, "value")
	options = [{"label": "Standard", "value": "Standard"}] + [{"label": n, "value": n} for n in names]
	if default:
		options.sort(key=lambda o: o["value"] != default)
	return options


# ---------------------------------------------------------------------------
# Dashboard analytics tabs
# ---------------------------------------------------------------------------


def _resolve_company(company: str | None = None):
	companies = frappe.get_list("Company", pluck="name", order_by="name")
	if company and company in companies:
		return company
	default = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	if default in companies:
		return default
	return companies[0] if len(companies) == 1 else None


def _currency_for(company):
	if company:
		return frappe.get_cached_value("Company", company, "default_currency")
	return frappe.db.get_single_value("Global Defaults", "default_currency")


def _last_12_months():
	first = frappe.utils.get_first_day(nowdate())
	months = []
	for offset in range(11, -1, -1):
		d = frappe.utils.add_months(first, -offset)
		months.append({"key": d.strftime("%Y-%m"), "label": frappe.utils.formatdate(d, "MMM")})
	return months


def _party_totals(doctype, party_field, company, start, end):
	"""Top parties by invoiced value. Uses get_list (dict-aggregates) so role AND
	user permissions apply. Returns (top_rows, unique_party_count)."""
	if not _can_read(doctype):
		return [], 0
	filters = [
		["docstatus", "=", 1],
		["is_return", "=", 0],
		["posting_date", ">=", start],
		["posting_date", "<=", end],
	]
	if company:
		filters.append(["company", "=", company])
	rows = frappe.get_list(
		doctype,
		filters=filters,
		fields=[party_field, {"SUM": "base_grand_total"}],
		group_by=party_field,
		limit_page_length=0,
	)
	key = "SUM(`base_grand_total`)"
	out = [{"label": r.get(party_field) or "—", "value": flt(r.get(key))} for r in rows]
	out.sort(key=lambda x: -x["value"])
	return out[:8], len(out)


def _item_totals(doctype, company, start, end):
	"""Top items by invoiced value."""
	if not _can_read(doctype):
		return []
	child = f"{doctype} Item"
	clause = " and p.company = %(company)s" if company else ""
	params = {"company": company, "start": start, "end": end}
	rows = frappe.db.sql(
		f"""select c.item_code as label, sum(c.qty) as qty, sum(c.base_amount) as value
		from `tab{child}` c inner join `tab{doctype}` p on p.name = c.parent
		where p.docstatus = 1 and p.is_return = 0
			and p.posting_date >= %(start)s and p.posting_date <= %(end)s{clause}
		group by c.item_code order by value desc limit 8""",
		params,
		as_dict=True,
	)
	return [{"label": r.label or "—", "value": flt(r.value), "sub": f"{flt(r.qty):g} qty"} for r in rows]


def _aging(doctype, party_field, company):
	"""Outstanding split into aging buckets + top outstanding parties."""
	if not _can_read(doctype):
		return {"buckets": [], "top": [], "total": 0.0}
	clause, params = _company_clause(company)
	rows = frappe.db.sql(
		f"""select
			case
				when datediff(curdate(), ifnull(due_date, posting_date)) <= 0 then 'Current'
				when datediff(curdate(), ifnull(due_date, posting_date)) <= 30 then '1-30'
				when datediff(curdate(), ifnull(due_date, posting_date)) <= 60 then '31-60'
				when datediff(curdate(), ifnull(due_date, posting_date)) <= 90 then '61-90'
				else '90+'
			end as bucket,
			sum(outstanding_amount) as total
		from `tab{doctype}`
		where docstatus = 1 and outstanding_amount > 0{clause}
		group by bucket""",
		params,
		as_dict=True,
	)
	found = {r.bucket: flt(r.total) for r in rows}
	order = ["Current", "1-30", "31-60", "61-90", "90+"]
	buckets = [{"label": b, "value": found.get(b, 0.0)} for b in order]

	top = frappe.db.sql(
		f"""select {party_field} as label, sum(outstanding_amount) as value
		from `tab{doctype}`
		where docstatus = 1 and outstanding_amount > 0{clause}
		group by {party_field} order by value desc limit 8""",
		params,
		as_dict=True,
	)
	return {
		"buckets": buckets,
		"top": [{"label": r.label or "—", "value": flt(r.value)} for r in top],
		"total": sum(b["value"] for b in buckets),
	}


def _invoice_analytics(doctype, party_field, company):
	company = _resolve_company(company)
	months = _last_12_months()
	start = months[0]["key"] + "-01"
	# Upper bound keeps monthly buckets, totals, counts and "top" lists consistent
	# (documents dated beyond this month would otherwise inflate the totals only).
	end = frappe.utils.get_last_day(nowdate())

	by_month = {}
	count = 0
	if _can_read(doctype):
		clause, params = _company_clause(company)
		params["start"] = start
		params["end"] = end
		rows = frappe.db.sql(
			f"""select date_format(posting_date, '%%Y-%%m') as ym, sum(base_grand_total) as total
			from `tab{doctype}`
			where docstatus = 1 and is_return = 0
				and posting_date >= %(start)s and posting_date <= %(end)s{clause}
			group by ym""",
			params,
			as_dict=True,
		)
		by_month = {r.ym: flt(r.total) for r in rows}
		count = (
			frappe.db.sql(
				f"""select count(name) from `tab{doctype}`
				where docstatus = 1 and is_return = 0
					and posting_date >= %(start)s and posting_date <= %(end)s{clause}""",
				params,
			)[0][0]
			or 0
		)

	monthly = [{"label": m["label"], "total": by_month.get(m["key"], 0.0)} for m in months]
	total_12m = sum(m["total"] for m in monthly)

	top_parties, unique_parties = _party_totals(doctype, party_field, company, start, end)

	largest = 0.0
	if _can_read(doctype):
		agg_filters = [
			["docstatus", "=", 1],
			["is_return", "=", 0],
			["posting_date", ">=", start],
			["posting_date", "<=", end],
		]
		if company:
			agg_filters.append(["company", "=", company])
		agg = frappe.get_list(doctype, filters=agg_filters, fields=[{"MAX": "base_grand_total"}])
		largest = flt(agg[0].get("MAX(`base_grand_total`)")) if agg else 0.0

	return {
		"company": company,
		"currency": _currency_for(company),
		"monthly": monthly,
		"total_12m": total_12m,
		"count_12m": count,
		"avg_value": (total_12m / count) if count else 0.0,
		"top_parties": top_parties,
		"unique_parties": unique_parties,
		"largest": largest,
		"top_items": _item_totals(doctype, company, start, end),
	}


@frappe.whitelist()
def get_sales_analytics(company: str | None = None) -> dict:
	return _invoice_analytics("Sales Invoice", "customer", company)


@frappe.whitelist()
def get_purchase_analytics(company: str | None = None) -> dict:
	return _invoice_analytics("Purchase Invoice", "supplier", company)


@frappe.whitelist()
def get_ar_ap_analytics(company: str | None = None) -> dict:
	company = _resolve_company(company)
	return {
		"company": company,
		"currency": _currency_for(company),
		"receivable": _aging("Sales Invoice", "customer", company),
		"payable": _aging("Purchase Invoice", "supplier", company),
	}


# Field names are fixed whitelists (never interpolated from user input) so the
# generic KPI query below is safe for any doctype the user may open.
_KPI_AMOUNT_FIELDS = ("base_grand_total", "grand_total", "base_paid_amount", "paid_amount", "total_debit")
_KPI_DATE_FIELDS = ("posting_date", "transaction_date", "schedule_date")


def _agg_count(doctype, filters):
	try:
		rows = frappe.get_list(doctype, filters=filters, fields=[{"COUNT": "*"}])
		return (rows[0].get("COUNT(*)") if rows else 0) or 0
	except Exception:
		return 0


def _agg_sum(doctype, filters, field):
	try:
		rows = frappe.get_list(doctype, filters=filters, fields=[{"SUM": field}])
		return flt(rows[0].get(f"SUM(`{field}`)")) if rows else 0.0
	except Exception:
		return 0.0


@frappe.whitelist()
def get_list_kpis(doctype: str, company: str | None = None) -> dict:
	"""Exactly four KPI cards above each list, adapted to the doctype's fields.
	Uses frappe.get_list aggregates so role AND user permissions apply."""
	if not frappe.db.exists("DocType", doctype) or not _can_read(doctype):
		return {"currency": None, "kpis": []}

	meta = frappe.get_meta(doctype)
	has_company = meta.has_field("company")
	company = _resolve_company(company) if has_company else None
	base = [["company", "=", company]] if (has_company and company) else []

	amount_field = next((f for f in _KPI_AMOUNT_FIELDS if meta.has_field(f)), None)
	date_field = next((f for f in _KPI_DATE_FIELDS if meta.has_field(f)), None)
	submittable = meta.is_submittable

	month_start = str(frappe.utils.get_first_day(nowdate()))
	month_end = str(frappe.utils.get_last_day(nowdate()))
	year_start = str(frappe.utils.get_year_start(nowdate()))

	def period(field, start, end=None):
		f = base + [[field, ">=", start]]
		if end:
			f.append([field, "<=", end])
		return f

	# Candidates in priority order; the first four available are shown.
	candidates = []
	if amount_field and date_field:
		submitted_month = period(date_field, month_start, month_end) + [["docstatus", "=", 1]]
		candidates.append({"label": "This month", "value": _agg_sum(doctype, submitted_month, amount_field), "money": True, "color": "green", "icon": "calendar"})
		candidates.append({"label": "This month (count)", "value": _agg_count(doctype, submitted_month), "money": False, "color": "blue", "icon": "file-text"})

	if meta.has_field("outstanding_amount"):
		f = base + [["docstatus", "=", 1], ["outstanding_amount", ">", 0]]
		candidates.append({"label": "Outstanding", "value": _agg_sum(doctype, f, "outstanding_amount"), "money": True, "color": "amber", "icon": "wallet"})

	if submittable:
		candidates.append({"label": "Drafts", "value": _agg_count(doctype, base + [["docstatus", "=", 0]]), "money": False, "color": "orange", "icon": "clock"})

	if amount_field and date_field:
		f = period(date_field, year_start) + [["docstatus", "=", 1]]
		candidates.append({"label": "This year", "value": _agg_sum(doctype, f, amount_field), "money": True, "color": "green", "icon": "trending-up"})

	if submittable:
		candidates.append({"label": "Submitted", "value": _agg_count(doctype, base + [["docstatus", "=", 1]]), "money": False, "color": "blue", "icon": "send"})

	if meta.has_field("disabled"):
		candidates.append({"label": "Active", "value": _agg_count(doctype, base + [["disabled", "=", 0]]), "money": False, "color": "green", "icon": "check-circle"})

	candidates.append({"label": "Total records", "value": _agg_count(doctype, base), "money": False, "color": "blue", "icon": "layers"})

	if meta.has_field("disabled"):
		candidates.append({"label": "Disabled", "value": _agg_count(doctype, base + [["disabled", "=", 1]]), "money": False, "color": "orange", "icon": "ban"})

	candidates.append({"label": "Added this month", "value": _agg_count(doctype, base + [["creation", ">=", month_start]]), "money": False, "color": "amber", "icon": "plus-circle"})

	return {"currency": _currency_for(company), "kpis": candidates[:4]}


# Marker that lets us find our cancellation note again among a document's comments.
# Stored as a Comment so no schema change / migration is needed, and the reason
# also shows up on the desk timeline.
_CANCEL_MARKER = "[kamil-cancel-reason]"


@frappe.whitelist()
def cancel_document(doctype: str, name: str, reason: str | None = None) -> dict:
	"""Cancel a submitted document (reverses its ledger entries), recording why.

	The reason is kept as a Comment tagged with ``_CANCEL_MARKER`` rather than a
	custom field, so this works on any DocType without a migration.
	"""
	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("Please give a reason for cancelling this document."))

	doc = frappe.get_doc(doctype, name)
	doc.cancel()

	frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Comment",
			"reference_doctype": doctype,
			"reference_name": name,
			"content": f"{_CANCEL_MARKER} {reason}",
		}
	).insert(ignore_permissions=True)

	return {"name": doc.name, "docstatus": doc.docstatus, "reason": reason}


@frappe.whitelist()
def get_cancellation_reason(doctype: str, name: str) -> dict:
	"""The recorded cancellation reason for a document, if we have one."""
	if not _can_read(doctype):
		return {}

	rows = frappe.get_all(
		"Comment",
		filters={
			"reference_doctype": doctype,
			"reference_name": name,
			"content": ("like", f"%{_CANCEL_MARKER}%"),
		},
		fields=["content", "owner", "creation"],
		order_by="creation desc",
		limit=1,
	)
	if not rows:
		return {}

	row = rows[0]
	return {
		"reason": (row.content or "").replace(_CANCEL_MARKER, "").strip(),
		"by": row.owner,
		"on": row.creation,
	}


def _link_options(fieldtype, options):
	"""Target doctype of a Link column, so the app can drill down from a cell.

	Only kept for link-ish columns — a Select's options are a newline-separated list
	of values and would only bloat the response.
	"""
	if fieldtype not in ("Link", "Dynamic Link"):
		return ""
	return (options or "").strip() if isinstance(options, str) else ""


@frappe.whitelist()
def run_report(report: str, filters: str | dict | None = None, limit: int = 500) -> dict:
	"""Run a standard query report and return normalised columns/rows for the app."""
	from frappe.desk.query_report import run as run_query_report

	try:
		filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	except Exception:
		filters = {}
	if not isinstance(filters, dict):
		filters = {}
	if not filters.get("company"):
		filters["company"] = _resolve_company(None)

	res = run_query_report(report_name=report, filters=filters, ignore_prepared_report=True) or {}

	columns = []
	for col in res.get("columns") or []:
		if isinstance(col, str):
			# legacy "Label:Type/Options:Width"
			parts = col.split(":")
			label = parts[0]
			spec = (parts[1] if len(parts) > 1 else "Data") or "Data"
			fieldtype = spec.split("/")[0] or "Data"
			options = spec.split("/")[1] if "/" in spec else ""
			columns.append(
				{
					"label": label,
					"fieldname": frappe.scrub(label),
					"fieldtype": fieldtype,
					"options": _link_options(fieldtype, options),
				}
			)
		else:
			label = col.get("label") or col.get("fieldname") or ""
			columns.append(
				{
					"label": label,
					"fieldname": col.get("fieldname") or frappe.scrub(label),
					"fieldtype": col.get("fieldtype") or "Data",
					"options": _link_options(col.get("fieldtype"), col.get("options")),
				}
			)

	rows = []
	for row in (res.get("result") or [])[: frappe.utils.cint(limit)]:
		if isinstance(row, dict):
			rows.append(row)
		elif isinstance(row, (list, tuple)):
			rows.append({columns[i]["fieldname"]: v for i, v in enumerate(row) if i < len(columns)})

	return {
		"columns": columns,
		"rows": rows,
		"currency": _currency_for(filters.get("company")),
		"truncated": len(res.get("result") or []) > frappe.utils.cint(limit),
	}


@frappe.whitelist()
def get_status_options(doctype: str) -> list:
	"""Select options of a doctype's `status` field, for the list filter."""
	if not frappe.db.exists("DocType", doctype) or not _can_read(doctype):
		return []
	field = frappe.get_meta(doctype).get_field("status")
	if not field or field.fieldtype != "Select" or not field.options:
		return []
	options = [o.strip() for o in field.options.split("\n") if o.strip()]
	return [{"label": "All statuses", "value": ""}] + [{"label": o, "value": o} for o in options]


def _pick_columns(all_columns: list, wanted: str | list | None) -> list:
	"""Narrow a column set to the fieldnames the user kept on screen."""
	if isinstance(wanted, str):
		try:
			wanted = frappe.parse_json(wanted)
		except Exception:
			wanted = [c.strip() for c in wanted.split(",") if c.strip()]
	if isinstance(wanted, list) and wanted:
		keep = set(wanted)
		return [c for c in all_columns if c.get("fieldname") in keep] or all_columns
	return all_columns


_NUMERIC_FIELDTYPES = ("Currency", "Float", "Int", "Percent")


def _display_value(value, column, currency) -> str:
	"""Value as the user sees it on screen — used by the CSV/PDF renderers."""
	if value is None or value == "":
		return ""
	fieldtype = column.get("fieldtype") or "Data"
	try:
		if fieldtype == "Currency":
			return frappe.utils.fmt_money(flt(value), currency=currency)
		if fieldtype in ("Float", "Percent"):
			return frappe.utils.fmt_money(flt(value), precision=2)
		if fieldtype == "Int":
			return str(cint(value))
		if fieldtype in ("Date", "Datetime"):
			return frappe.utils.formatdate(value)
	except Exception:
		return str(value)
	# Query reports may hand back anchor tags; the export wants plain text.
	return re.sub(r"<[^>]*>", "", str(value)).strip()


def _report_pdf(title: str, columns: list, rows: list, currency: str | None) -> bytes:
	from frappe.utils.pdf import get_pdf

	head = "".join(
		'<th class="{cls}">{label}</th>'.format(
			cls="num" if c.get("fieldtype") in _NUMERIC_FIELDTYPES else "",
			label=frappe.utils.escape_html(str(c.get("label") or c.get("fieldname") or "")),
		)
		for c in columns
	)

	body = []
	for row in rows:
		cells = []
		for c in columns:
			numeric = c.get("fieldtype") in _NUMERIC_FIELDTYPES
			text = frappe.utils.escape_html(_display_value(row.get(c["fieldname"]), c, currency))
			cells.append(f'<td class="{"num" if numeric else ""}">{text}</td>')
		# Report rows carry their own indentation for tree-style statements.
		indent = cint(row.get("indent"))
		style = f' style="padding-left:{indent * 12}px"' if indent else ""
		body.append("<tr>" + "".join(cells).replace("<td", f"<td{style}", 1) + "</tr>")

	html = f"""
	<style>
		body {{ font-family: Helvetica, Arial, sans-serif; font-size: 8pt; color: #1f272e; }}
		h3 {{ margin: 0 0 2px 0; font-size: 12pt; }}
		.meta {{ color: #6b7580; font-size: 7.5pt; margin-bottom: 8px; }}
		table {{ width: 100%; border-collapse: collapse; }}
		th {{ background: #f4f5f6; text-align: left; font-weight: 600; }}
		th, td {{ border: 0.5pt solid #dfe1e3; padding: 3px 5px; }}
		tbody tr:nth-child(even) td {{ background: #fafbfc; }}
		.num {{ text-align: right; }}
	</style>
	<h3>{frappe.utils.escape_html(title)}</h3>
	<div class="meta">{frappe.utils.escape_html(frappe.utils.formatdate(nowdate()))} · {len(rows)} rows</div>
	<table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>
	"""

	# Landscape: these reports are wide, and portrait would shrink them to nothing.
	return get_pdf(html, {"orientation": "Landscape", "page-size": "A4", "margin-top": "12mm"})


def _stream_export(title: str, columns: list, rows: list, file_format: str, currency: str | None) -> None:
	"""Put a CSV / Excel / PDF rendering of a report on the current response."""
	safe_name = (title or "report").replace(" ", "_").replace("/", "-")
	fmt = (file_format or "excel").lower()

	if fmt == "pdf":
		frappe.response["filename"] = f"{safe_name}.pdf"
		frappe.response["filecontent"] = _report_pdf(title, columns, rows, currency)
		frappe.response["type"] = "pdf"
		return

	matrix = [[c.get("label") or c.get("fieldname") for c in columns]]
	for row in rows:
		matrix.append([("" if row.get(c["fieldname"]) is None else row.get(c["fieldname"])) for c in columns])

	if fmt == "csv":
		from frappe.utils.csvutils import to_csv

		frappe.response["result"] = to_csv(matrix)
		frappe.response["type"] = "csv"
		frappe.response["doctype"] = safe_name
		return

	from frappe.utils.xlsxutils import make_xlsx

	xlsx_file = make_xlsx(matrix, safe_name)
	frappe.response["filename"] = f"{safe_name}.xlsx"
	frappe.response["filecontent"] = xlsx_file.getvalue()
	frappe.response["type"] = "binary"


@frappe.whitelist()
def export_report(
	report: str,
	filters: str | dict | None = None,
	file_format: str = "Excel",
	columns: str | list | None = None,
) -> None:
	"""Stream a query report as .xlsx, .csv or .pdf download.

	`columns` optionally restricts the export to a subset of fieldnames, so a download
	matches the columns the user chose to keep on screen.
	"""
	data = run_report(report, filters, limit=100000)
	_stream_export(
		report,
		_pick_columns(data.get("columns") or [], columns),
		data.get("rows") or [],
		file_format,
		data.get("currency"),
	)


@frappe.whitelist()
def export_doc_report(
	doctype: str,
	filters: str | dict | None = None,
	file_format: str = "Excel",
	columns: str | list | None = None,
) -> None:
	"""Same downloads as the query reports, for a list view's Report tab."""
	data = get_doc_report(doctype, filters, limit=100000)
	_stream_export(
		doctype,
		_pick_columns(data.get("columns") or [], columns),
		data.get("rows") or [],
		file_format,
		data.get("currency"),
	)


_SELLING_DOCTYPES = ("Quotation", "Sales Order", "Delivery Note", "Sales Invoice")


@frappe.whitelist()
def get_item_rate(
	item_code: str,
	doctype: str | None = None,
	party: str | None = None,
	company: str | None = None,
	price_list: str | None = None,
) -> dict:
	"""Best-effort rate for an item when building a document in the app.

	Order: party/default price list -> Item Price (date-valid) -> item defaults
	(standard rate for selling, last purchase rate for buying) -> valuation rate.
	"""
	if not item_code or not frappe.db.exists("Item", item_code):
		return {"rate": 0, "price_list": None}

	selling = (doctype or "") in _SELLING_DOCTYPES
	company = company or _resolve_company(None)

	if not price_list and party:
		party_type = "Customer" if selling else "Supplier"
		if frappe.db.exists(party_type, party):
			price_list = frappe.db.get_value(party_type, party, "default_price_list")
	if not price_list:
		price_list = (
			frappe.db.get_single_value("Selling Settings", "selling_price_list")
			if selling
			else frappe.db.get_single_value("Buying Settings", "buying_price_list")
		)

	rate = 0.0
	today = nowdate()
	if price_list:
		rows = frappe.get_all(
			"Item Price",
			filters={"item_code": item_code, "price_list": price_list},
			fields=["price_list_rate", "valid_from", "valid_upto"],
			order_by="valid_from desc",
			limit_page_length=20,
		)
		for r in rows:
			if r.valid_from and str(r.valid_from) > today:
				continue
			if r.valid_upto and str(r.valid_upto) < today:
				continue
			rate = flt(r.price_list_rate)
			if rate:
				break

	item = frappe.db.get_value(
		"Item", item_code, ["item_name", "stock_uom", "standard_rate", "last_purchase_rate"], as_dict=True
	) or frappe._dict()

	if not rate:
		rate = flt(item.standard_rate) if selling else flt(item.last_purchase_rate)

	if not rate:
		bin_filters = {"item_code": item_code}
		if company:
			warehouses = frappe.get_all("Warehouse", filters={"company": company, "is_group": 0}, pluck="name")
			if warehouses:
				bin_filters["warehouse"] = ["in", warehouses]
		rate = flt(
			frappe.db.get_value("Bin", bin_filters, "valuation_rate", order_by="valuation_rate desc")
		)

	return {
		"rate": flt(rate),
		"price_list": price_list,
		"item_name": item.item_name,
		"uom": item.stock_uom,
		"warehouse": _default_item_warehouse(item_code, company, selling),
	}


def _default_item_warehouse(item_code: str, company: str | None, selling: bool) -> str | None:
	"""Where a line for this item should default to.

	Item Defaults first (that is where a warehouse is set per company), then the
	site-wide Stock Settings default. Both are checked against the company so a line
	never defaults to another company's store.
	"""
	if not company:
		return None

	row = frappe.db.get_value(
		"Item Default",
		{"parent": item_code, "company": company},
		["default_warehouse", "buying_cost_center", "selling_cost_center"],
		as_dict=True,
	)
	warehouse = (row or {}).get("default_warehouse")
	if warehouse:
		return warehouse

	default_wh = frappe.db.get_single_value("Stock Settings", "default_warehouse")
	if default_wh and frappe.db.get_value("Warehouse", default_wh, "company") == company:
		return default_wh
	return None


@frappe.whitelist()
def get_inventory_analytics(company: str | None = None) -> dict:
	"""Stock KPIs + distribution. Uses get_list throughout so permissions apply."""
	company = _resolve_company(company)
	empty = {
		"company": company,
		"currency": _currency_for(company),
		"total_value": 0.0,
		"active_skus": 0,
		"stocked_skus": 0,
		"out_of_stock": 0,
		"low_stock": 0,
		"by_group": [],
		"top_items": [],
	}
	if not (_can_read("Bin") and _can_read("Item")):
		return empty

	bin_filters = {}
	if company:
		warehouses = frappe.get_all("Warehouse", filters={"company": company, "is_group": 0}, pluck="name")
		if warehouses:
			bin_filters["warehouse"] = ["in", warehouses]

	bins = frappe.get_list(
		"Bin",
		filters=bin_filters,
		fields=["item_code", {"SUM": "actual_qty"}, {"SUM": "stock_value"}],
		group_by="item_code",
		limit_page_length=0,
	)
	qty_key, val_key = "SUM(`actual_qty`)", "SUM(`stock_value`)"
	rows = [
		{"item": b.get("item_code"), "qty": flt(b.get(qty_key)), "value": flt(b.get(val_key))}
		for b in bins
		if b.get("item_code")
	]

	items = {}
	codes = [r["item"] for r in rows]
	if codes:
		for it in frappe.get_list(
			"Item",
			filters={"name": ["in", codes]},
			fields=["name", "item_name", "item_group", "safety_stock"],
			limit_page_length=0,
		):
			items[it.name] = it

	active = frappe.get_list("Item", filters={"disabled": 0}, fields=[{"COUNT": "*"}])
	active_skus = (active[0].get("COUNT(*)") if active else 0) or 0

	by_group = {}
	for r in rows:
		group = (items.get(r["item"]) or {}).get("item_group") or "—"
		by_group[group] = by_group.get(group, 0.0) + r["value"]

	def _low(r):
		safety = flt((items.get(r["item"]) or {}).get("safety_stock"))
		return r["qty"] > 0 and safety > 0 and r["qty"] <= safety

	top = sorted(rows, key=lambda r: -r["value"])[:8]
	return {
		"company": company,
		"currency": _currency_for(company),
		"total_value": sum(r["value"] for r in rows),
		"active_skus": active_skus,
		"stocked_skus": len(rows),
		"out_of_stock": len([r for r in rows if r["qty"] <= 0]),
		"low_stock": len([r for r in rows if _low(r)]),
		"by_group": sorted(
			[{"label": k, "value": v} for k, v in by_group.items()], key=lambda x: -x["value"]
		)[:8],
		"top_items": [
			{
				"label": (items.get(r["item"]) or {}).get("item_name") or r["item"],
				"value": r["value"],
				"sub": f"{r['qty']:g} in stock",
			}
			for r in top
		],
	}


# doctype -> list of (label, target doctype, mapping "module.func") transitions
# Order -> Invoice only. Delivery Notes, Purchase Receipts and Quotations are not part
# of this app's flow: the invoice carries the stock movement itself via `update_stock`,
# which is set on every invoice made here (see _stock_updating_invoice).
_DOC_TRANSITIONS = {
	"Sales Order": [
		("Sales Invoice", "Sales Invoice", "erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice"),
	],
	"Purchase Order": [
		("Purchase Invoice", "Purchase Invoice", "erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_invoice"),
	],
}

_STOCK_INVOICES = ("Sales Invoice", "Purchase Invoice")


def _stock_updating_invoice(doc) -> None:
	"""Make an invoice move stock itself.

	With no Delivery Note or Purchase Receipt in the flow, an invoice that does not
	update stock would leave the goods where they were — billed but never shipped or
	received. A warehouse is required for it to post, so this is skipped when there is
	nothing to post against.
	"""
	if doc.doctype not in _STOCK_INVOICES or not doc.meta.has_field("update_stock"):
		return
	if not any(row.get("warehouse") for row in (doc.get("items") or [])) and not doc.get("set_warehouse"):
		return
	doc.update_stock = 1


@frappe.whitelist()
def get_doc_transitions(doctype: str) -> list:
	"""Documents that can be created FROM a given doctype (needs create perm on target)."""
	out = []
	for label, target, _method in _DOC_TRANSITIONS.get(doctype, []):
		if frappe.has_permission(target, "create"):
			out.append({"label": label, "target": target})
	return out


def _scalar(value):
	"""A JSON-safe version of a field value, or None if it cannot travel.

	Dates and Decimals arrive as objects; dropping them would silently lose the
	posting date or an amount, so they are stringified rather than skipped.
	"""
	if isinstance(value, (str, int, float)):
		return value
	if isinstance(value, (datetime.date, datetime.datetime, datetime.time)):
		return str(value)
	if isinstance(value, decimal.Decimal):
		return flt(value)
	return None


def _plain_row(row) -> dict:
	"""A child row as a plain dict.

	`hasattr(row, "as_dict")` is not enough: frappe._dict answers every attribute with
	None rather than raising, so the check passes and the call then fails.
	"""
	if isinstance(row, dict):
		return dict(row)
	as_dict = getattr(row, "as_dict", None)
	return as_dict() if callable(as_dict) else dict(row)


@frappe.whitelist()
def get_next_document_draft(doctype: str, name: str, target: str) -> dict:
	"""Map a source document onto the next one and return it **unsaved**.

	The app used to insert the mapped draft straight away, which left a half-considered
	document behind whenever someone changed their mind. Instead the mapped values come
	back and the create form opens on top of them, as the desk does.
	"""
	transition = next((t for t in _DOC_TRANSITIONS.get(doctype, []) if t[1] == target), None)
	if not transition:
		frappe.throw(_("Cannot create {0} from {1}.").format(target, doctype))

	frappe.has_permission(doctype, "read", doc=name, throw=True)
	frappe.has_permission(target, "create", throw=True)

	doc = frappe.get_attr(transition[2])(name)
	_stock_updating_invoice(doc)

	values = {}
	for field, value in doc.as_dict().items():
		if value in (None, "") or field.startswith("_"):
			continue
		if isinstance(value, list):
			# Every child table travels, not just the lines: taxes, compartments and the
			# rest are part of what the mapping produced, and dropping them would quietly
			# change the document the user thought they were creating.
			rows = [
				{
					k: _scalar(v)
					for k, v in _plain_row(row).items()
					if v not in (None, "") and not k.startswith("_") and k not in _CHILD_META_FIELDS
				}
				for row in value
			]
			if rows:
				values[field] = rows
		else:
			scalar = _scalar(value)
			if scalar is not None:
				values[field] = scalar

	for field in _DOC_META_FIELDS:
		values.pop(field, None)

	return {"doctype": target, "values": values}


_DOC_META_FIELDS = ("name", "owner", "creation", "modified", "modified_by", "docstatus", "idx", "doctype")
_CHILD_META_FIELDS = ("name", "owner", "creation", "modified", "modified_by", "docstatus", "idx", "parent",
	"parentfield", "parenttype", "doctype")


@frappe.whitelist()
def make_next_document(doctype: str, name: str, target: str) -> dict:
	"""Map a source document to the next document in its flow and insert a draft."""
	transition = next(
		(t for t in _DOC_TRANSITIONS.get(doctype, []) if t[1] == target), None
	)
	if not transition:
		frappe.throw(_("Cannot create {0} from {1}.").format(target, doctype))

	# read source, create target
	frappe.has_permission(doctype, "read", doc=name, throw=True)
	frappe.has_permission(target, "create", throw=True)

	method = frappe.get_attr(transition[2])
	doc = method(name)
	_stock_updating_invoice(doc)
	doc.insert()
	return {"name": doc.name, "doctype": doc.doctype}


@frappe.whitelist()
def get_list_analytics(doctype: str, company: str | None = None) -> dict:
	"""Per-list Insights tab: KPIs + status split + top parties + 6-month trend.
	Aggregates use frappe.get_list so role AND user permissions apply."""
	empty = {"currency": None, "kpis": [], "status": [], "top_parties": [], "monthly": [], "party_type": ""}
	if not frappe.db.exists("DocType", doctype) or not _can_read(doctype):
		return empty

	meta = frappe.get_meta(doctype)
	has_company = meta.has_field("company")
	company = _resolve_company(company) if has_company else None
	base = [["company", "=", company]] if (has_company and company) else []

	amount_field = next((f for f in _KPI_AMOUNT_FIELDS if meta.has_field(f)), None)
	date_field = next((f for f in _KPI_DATE_FIELDS if meta.has_field(f)), None)
	party_field = next((f for f in ("customer", "supplier", "party_name") if meta.has_field(f)), None)
	status_field = meta.get_field("status")
	has_status = bool(status_field and status_field.fieldtype == "Select")

	kpis = get_list_kpis(doctype, company).get("kpis", [])

	status_rows = []
	if has_status:
		rows = frappe.get_list(
			doctype, filters=base + [["docstatus", "<", 2]], fields=["status", {"COUNT": "*"}],
			group_by="status", limit_page_length=0,
		)
		status_rows = [{"label": r.get("status") or "—", "value": r.get("COUNT(*)") or 0} for r in rows if r.get("status")]

	top_parties = []
	if party_field and amount_field:
		rows = frappe.get_list(
			doctype, filters=base + [["docstatus", "=", 1]], fields=[party_field, {"SUM": amount_field}],
			group_by=party_field, limit_page_length=0,
		)
		sk = f"SUM(`{amount_field}`)"
		top_parties = sorted(
			[{"label": r.get(party_field) or "—", "value": flt(r.get(sk))} for r in rows],
			key=lambda x: -x["value"],
		)[:8]

	monthly = []
	if amount_field and date_field:
		first = frappe.utils.get_first_day(nowdate())
		sk = f"SUM(`{amount_field}`)"
		for off in range(5, -1, -1):
			m0 = frappe.utils.add_months(first, -off)
			m1 = frappe.utils.get_last_day(m0)
			rows = frappe.get_list(
				doctype,
				filters=base + [["docstatus", "=", 1], [date_field, ">=", str(m0)], [date_field, "<=", str(m1)]],
				fields=[{"SUM": amount_field}],
			)
			monthly.append({"label": frappe.utils.formatdate(m0, "MMM"), "total": flt(rows[0].get(sk)) if rows else 0})

	party_type = "Customer" if party_field == "customer" else ("Supplier" if party_field == "supplier" else "")
	return {
		"currency": _currency_for(company),
		"kpis": kpis,
		"status": status_rows,
		"top_parties": top_parties,
		"monthly": monthly,
		"party_type": party_type,
	}


def has_app_permission() -> bool:
	"""Whether to show the Kamil tile on the desk's apps screen.

	Called by Frappe's apps screen (see `add_to_apps_screen` in hooks.py). Anyone
	signed in may open the app — every screen inside it re-checks permissions and
	shows only what the user can actually read.
	"""
	return bool(frappe.session.user and frappe.session.user != "Guest")


@frappe.whitelist()
def get_app_links() -> dict:
	"""Optional external app shortcuts shown in the UI (only if installed)."""
	installed = frappe.get_installed_apps() or []
	return {"raven": "/raven" if "raven" in installed else None}


_REPORT_SAFE_FIELDTYPES = (
	"Data", "Select", "Link", "Dynamic Link", "Date", "Datetime", "Time",
	"Currency", "Float", "Int", "Percent", "Check", "Small Text", "Read Only",
)
_REPORT_EXTRA_FIELDS = (
	"status", "posting_date", "transaction_date", "schedule_date", "due_date",
	"grand_total", "outstanding_amount", "paid_amount", "total_debit", "item_group", "stock_uom",
)


@frappe.whitelist()
def get_doc_report(doctype: str, filters: str | dict | None = None, limit: int = 200) -> dict:
	"""Frappe-style report view for a doctype: wider column set + column totals.
	Rows come from frappe.get_list, so role AND user permissions apply."""
	empty = {"columns": [], "rows": [], "totals": {}, "currency": None, "truncated": False}
	if not frappe.db.exists("DocType", doctype) or not _can_read(doctype):
		return empty

	try:
		filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	except Exception:
		filters = {}
	if not isinstance(filters, dict):
		filters = {}

	meta = frappe.get_meta(doctype)
	has_company = meta.has_field("company")
	company = _resolve_company(filters.get("company")) if has_company else None
	if has_company and company:
		filters["company"] = company

	columns = [{"label": "ID", "fieldname": "name", "fieldtype": "Data"}]
	seen = {"name"}

	def add(df):
		if not df or df.fieldname in seen:
			return
		if df.fieldtype not in _REPORT_SAFE_FIELDTYPES:
			return
		seen.add(df.fieldname)
		columns.append(
			{
				"label": _(df.label or df.fieldname),
				"fieldname": df.fieldname,
				"fieldtype": df.fieldtype,
				"options": _link_options(df.fieldtype, df.options),
			}
		)

	for df in meta.fields:
		if df.in_list_view:
			add(df)
	for fieldname in _REPORT_EXTRA_FIELDS:
		add(meta.get_field(fieldname))

	columns = columns[:12]
	fieldnames = [c["fieldname"] for c in columns]

	rows = frappe.get_list(
		doctype,
		filters=filters,
		fields=fieldnames,
		order_by="modified desc",
		limit_page_length=frappe.utils.cint(limit) + 1,
	)
	truncated = len(rows) > frappe.utils.cint(limit)
	rows = rows[: frappe.utils.cint(limit)]

	totals = {}
	for c in columns:
		if c["fieldtype"] in ("Currency", "Float", "Int", "Percent") and c["fieldname"] != "name":
			totals[c["fieldname"]] = flt(sum(flt(r.get(c["fieldname"])) for r in rows))

	return {
		"columns": columns,
		"rows": rows,
		"totals": totals,
		"currency": _currency_for(company),
		"truncated": truncated,
	}


# ---------------------------------------------------------------------------
# Navigation permissions
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_nav_permissions(doctypes: str | list | None = None) -> dict:
	"""Per-doctype read/create flags, so the sidebar only offers what the user may open.

	Unknown or uninstalled doctypes come back as not-readable rather than raising,
	which lets the frontend list entries for optional apps unconditionally.
	"""
	if isinstance(doctypes, str):
		try:
			doctypes = frappe.parse_json(doctypes)
		except Exception:
			doctypes = [d.strip() for d in doctypes.split(",") if d.strip()]
	if not isinstance(doctypes, list):
		return {}

	out = {}
	for doctype in doctypes:
		if not isinstance(doctype, str) or not doctype:
			continue
		try:
			if not frappe.db.exists("DocType", doctype):
				out[doctype] = {"read": False, "create": False}
				continue
			out[doctype] = {
				"read": bool(frappe.has_permission(doctype, "read")),
				"create": bool(frappe.has_permission(doctype, "create")),
			}
		except Exception:
			out[doctype] = {"read": False, "create": False}
	return out


@frappe.whitelist()
def get_permitted_reports(reports: str | list | None = None) -> dict:
	"""Which of the app's reports the user may run.

	A query report is allowed when the user can read the report's reference
	DocType and the Report record itself is not restricted away from them.
	"""
	if isinstance(reports, str):
		try:
			reports = frappe.parse_json(reports)
		except Exception:
			reports = [r.strip() for r in reports.split(",") if r.strip()]
	if not isinstance(reports, list):
		return {}

	out = {}
	for report in reports:
		if not isinstance(report, str) or not report:
			continue
		try:
			if not frappe.db.exists("Report", report):
				out[report] = False
				continue
			ref_doctype = frappe.db.get_value("Report", report, "ref_doctype")
			out[report] = bool(not ref_doctype or frappe.has_permission(ref_doctype, "read"))
		except Exception:
			out[report] = False
	return out


# ---------------------------------------------------------------------------
# Notifications (pending work shown in the header bell)
# ---------------------------------------------------------------------------

# Each entry: doctype, label, the statuses it counts, and a colour. The list view is
# deep-linked with exactly these statuses, so the list always matches the count clicked.
_NOTIFICATION_SOURCES = (
	("Sales Invoice", "Overdue invoices", ("Overdue",), "red"),
	("Sales Invoice", "Unpaid invoices", ("Unpaid", "Partly Paid"), "orange"),
	("Purchase Invoice", "Overdue bills", ("Overdue",), "red"),
	("Purchase Invoice", "Unpaid bills", ("Unpaid", "Partly Paid"), "orange"),
	("Sales Order", "Orders to deliver", ("To Deliver", "To Deliver and Bill"), "amber"),
	("Purchase Order", "Orders to receive", ("To Receive", "To Receive and Bill"), "amber"),
)


# Notification Log types, mapped onto the app's indicator colours.
_SYSTEM_NOTIFICATION_COLORS = {
	"Mention": "blue",
	"Assignment": "orange",
	"Share": "blue",
	"Alert": "red",
	"Energy Point": "green",
}
_SYSTEM_NOTIFICATION_LIMIT = 20


def _plain_text(html: str | None) -> str:
	"""Notification subjects arrive as HTML fragments; the bell shows plain text."""
	text = re.sub(r"<[^>]*>", " ", html or "")
	text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
	return re.sub(r"\s+", " ", text).strip()


def _system_notifications(limit: int = _SYSTEM_NOTIFICATION_LIMIT) -> list:
	"""The signed-in user's own Notification Log entries — the same mentions,
	assignments, shares and alerts the desk bell shows."""
	if not frappe.db.exists("DocType", "Notification Log"):
		return []

	try:
		rows = frappe.get_all(
			"Notification Log",
			filters={"for_user": frappe.session.user},
			fields=[
				"name",
				"subject",
				"email_content",
				"type",
				"document_type",
				"document_name",
				"from_user",
				"read",
				"link",
				"creation",
			],
			order_by="creation desc",
			limit_page_length=cint(limit),
		)
	except Exception:
		return []

	senders = {}
	for row in rows:
		if row.from_user and row.from_user not in senders:
			senders[row.from_user] = frappe.db.get_value("User", row.from_user, "full_name") or row.from_user

	return [
		{
			"name": row.name,
			"subject": _plain_text(row.subject),
			"email_content": row.email_content or "",
			"type": row.type or "Alert",
			"doctype": row.document_type,
			"document": row.document_name,
			"from_user": row.from_user,
			"from_user_name": senders.get(row.from_user),
			"read": cint(row.read),
			"link": row.link,
			"creation": str(row.creation),
			"color": _SYSTEM_NOTIFICATION_COLORS.get(row.type or "", "gray"),
		}
		for row in rows
	]


@frappe.whitelist()
def get_notifications() -> dict:
	"""What the header bell shows: work that needs attention, plus the user's own
	system notifications (mentions, assignments, shares, alerts).

	Every count goes through frappe.get_list, so role and user permissions apply
	and a user only ever sees totals for records they could open themselves. The
	system notifications are filtered to the session user, so nobody sees anyone
	else's.
	"""
	items = []
	for doctype, label, statuses, color in _NOTIFICATION_SOURCES:
		if not frappe.db.exists("DocType", doctype) or not _can_read(doctype):
			continue
		count = _agg_count(doctype, {"docstatus": 1, "status": ("in", list(statuses))})
		if not count:
			continue
		items.append(
			{
				"key": f"{frappe.scrub(doctype)}-{frappe.scrub(label)}",
				"label": _(label),
				"count": count,
				"doctype": doctype,
				"status": ",".join(statuses),
				"color": color,
			}
		)

	system = _system_notifications()
	unread = len([n for n in system if not n["read"]])
	pending = sum(i["count"] for i in items)

	return {
		# `total` stays the badge number: pending work plus anything unread.
		"total": pending + unread,
		"pending_total": pending,
		"unread": unread,
		"items": items,
		"system": system,
	}


@frappe.whitelist()
def mark_notification_read(name: str) -> dict:
	"""Mark one of the user's own notifications as read.

	Frappe's own endpoint marks any log by name; this one refuses anything that is
	not addressed to the session user.
	"""
	if not name:
		return {"read": False}

	for_user = frappe.db.get_value("Notification Log", name, "for_user")
	if for_user != frappe.session.user:
		frappe.throw(_("Not your notification."), frappe.PermissionError)

	frappe.db.set_value("Notification Log", name, "read", 1, update_modified=False)
	return {"read": True, "name": name}


@frappe.whitelist()
def mark_all_notifications_read() -> dict:
	"""Clear the unread flag on every notification addressed to this user."""
	names = frappe.get_all(
		"Notification Log", filters={"for_user": frappe.session.user, "read": 0}, pluck="name"
	)
	if names:
		frappe.db.set_value("Notification Log", {"name": ("in", names)}, "read", 1, update_modified=False)
	return {"read": len(names)}


# ---------------------------------------------------------------------------
# Report filter helpers
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_fiscal_years(company: str | None = None) -> list:
	"""Fiscal years the report filters may offer, newest first.

	Scoped to the company, because a Fiscal Year can be restricted to specific
	companies — offering one that does not apply is how a report ends up reporting
	that a date "is not in any active Fiscal Year".
	"""
	if not _can_read("Fiscal Year"):
		return []

	company = _resolve_company(company)
	rows = []
	try:
		from erpnext.accounts.utils import get_fiscal_years as _erpnext_fiscal_years

		rows = _erpnext_fiscal_years(company=company, as_dict=True, raise_on_missing=False) or []
	except Exception:
		rows = frappe.get_all(
			"Fiscal Year",
			filters={"disabled": 0},
			fields=["name", "year_start_date", "year_end_date"],
			order_by="year_start_date desc",
			limit=20,
		)

	return [
		{
			"label": r.get("name"),
			"value": r.get("name"),
			"start_date": str(r.get("year_start_date") or ""),
			"end_date": str(r.get("year_end_date") or ""),
		}
		for r in rows
	][:20]


@frappe.whitelist()
def get_current_fiscal_year(company: str | None = None) -> dict:
	"""The fiscal year containing today, with its bounds — the report filter defaults.

	Asks ERPNext first so company-restricted fiscal years are honoured. Falls back to
	the newest fiscal year on file, then to the calendar year, so filters still get
	sensible dates on a site whose fiscal years do not cover today.
	"""
	company = _resolve_company(company)

	try:
		from erpnext.accounts.utils import get_fiscal_year as _erpnext_fiscal_year

		row = _erpnext_fiscal_year(nowdate(), company=company, as_dict=True, raise_on_missing=False)
		if row and row.get("name"):
			return {
				"name": row.get("name"),
				"start_date": str(row.get("year_start_date")),
				"end_date": str(row.get("year_end_date")),
			}
	except Exception:
		pass

	# Today sits outside every fiscal year (common on demo data) — fall back to the
	# most recent one rather than to dates no report can work with.
	try:
		rows = get_fiscal_years(company)
		if rows and rows[0].get("start_date"):
			return {
				"name": rows[0]["value"],
				"start_date": rows[0]["start_date"],
				"end_date": rows[0]["end_date"],
			}
	except Exception:
		pass

	year = frappe.utils.getdate(nowdate()).year
	return {"name": None, "start_date": f"{year}-01-01", "end_date": f"{year}-12-31"}

# ---------------------------------------------------------------------------
# Payroll
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_payroll_actions(name: str) -> dict:
	"""Where a payroll entry is in its run, and what can be done next.

	The run is HRMS's: fill the employees, create the slips, submit them. This only
	reports the state so the app can offer the right button.
	"""
	if not frappe.db.exists("DocType", "Payroll Entry"):
		return {"supported": False}

	entry = frappe.get_doc("Payroll Entry", name)
	entry.check_permission("read")

	slips = frappe.get_all(
		"Salary Slip",
		filters={"payroll_entry": name, "docstatus": ("<", 2)},
		fields=["name", "docstatus", "net_pay"],
	)
	drafts = [s for s in slips if cint(s.docstatus) == 0]

	return {
		"supported": True,
		"name": entry.name,
		"docstatus": cint(entry.docstatus),
		"status": entry.get("status"),
		"employees": len(entry.get("employees") or []),
		"slips": len(slips),
		"draft_slips": len(drafts),
		"submitted_slips": len(slips) - len(drafts),
		"net_pay": flt(sum(flt(s.net_pay) for s in slips)),
		"can_fill": cint(entry.docstatus) == 0,
		"can_submit_entry": cint(entry.docstatus) == 0 and bool(entry.get("employees")),
		"can_create_slips": cint(entry.docstatus) == 1 and not slips,
		"can_submit_slips": bool(drafts),
	}


@frappe.whitelist()
def run_payroll_action(name: str, action: str) -> dict:
	"""Drive one step of the payroll run: employees, slips, submission.

	Each step is HRMS's own method — this only routes to it, so the payroll behaves
	exactly as it does on the desk.
	"""
	entry = frappe.get_doc("Payroll Entry", name)
	entry.check_permission("write" if action != "submit_slips" else "submit")

	if action == "fill_employees":
		employees = entry.fill_employee_details()
		entry.save()
		return {"action": action, "employees": len(employees or entry.get("employees") or [])}

	if action == "submit_entry":
		if cint(entry.docstatus) == 0:
			entry.submit()
		return {"action": action, "docstatus": cint(entry.docstatus)}

	if action == "create_slips":
		if cint(entry.docstatus) != 1:
			frappe.throw(_("Submit the payroll entry before creating salary slips."))
		entry.create_salary_slips()
		return {"action": action, "slips": frappe.db.count("Salary Slip", {"payroll_entry": name})}

	if action == "submit_slips":
		entry.submit_salary_slips()
		return {
			"action": action,
			"submitted": frappe.db.count("Salary Slip", {"payroll_entry": name, "docstatus": 1}),
		}

	frappe.throw(_("Unknown payroll action: {0}").format(action))


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------


@frappe.whitelist()
def assign_document(doctype: str, name: str, user: str, description: str | None = None) -> dict:
	"""Assign a document to somebody — the same ToDo the desk creates."""
	frappe.has_permission(doctype, "read", doc=name, throw=True)
	if not frappe.db.exists("User", user):
		frappe.throw(_("{0} is not a user on this site.").format(user))

	from frappe.desk.form.assign_to import add

	add(
		{
			"assign_to": [user],
			"doctype": doctype,
			"name": name,
			"description": description or _("Please look at {0} {1}").format(_(doctype), name),
		}
	)
	return {"assigned_to": user}


@frappe.whitelist()
def get_assignments(doctype: str, name: str) -> list:
	"""Who a document is currently assigned to."""
	frappe.has_permission(doctype, "read", doc=name, throw=True)
	rows = frappe.get_all(
		"ToDo",
		filters={"reference_type": doctype, "reference_name": name, "status": ("!=", "Cancelled")},
		fields=["name", "allocated_to", "status", "description"],
	)
	names = {r.allocated_to for r in rows if r.allocated_to}
	full = {u: frappe.db.get_value("User", u, "full_name") or u for u in names}
	return [
		{"todo": r.name, "user": r.allocated_to, "full_name": full.get(r.allocated_to), "status": r.status}
		for r in rows
	]
