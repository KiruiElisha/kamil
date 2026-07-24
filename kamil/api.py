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
def list_modes_of_payment():
	rows = frappe.get_list("Mode of Payment", filters={"enabled": 1}, pluck="name", order_by="name")
	return [{"value": n, "label": n} for n in rows]


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
def record_payment(invoice_type: str, invoice_name: str, amount: float | str | None = None, mode_of_payment: str | None = None):
	"""Create a DRAFT Payment Entry against an existing invoice and return its name."""
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	dt = "Sales Invoice" if invoice_type == "Sales" else "Purchase Invoice"
	pe = get_payment_entry(dt, invoice_name)
	if mode_of_payment:
		pe.mode_of_payment = mode_of_payment
	if amount:
		amount = flt(amount)
		pe.paid_amount = amount
		pe.received_amount = amount
		if pe.references:
			pe.references[0].allocated_amount = amount
	pe.insert()
	return {"name": pe.name, "doctype": pe.doctype}


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
	doc.insert()
	return {"name": doc.name, "doctype": doc.doctype}


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

	return {"company": company, "warehouse": warehouse}


@frappe.whitelist()
def submit_document(doctype: str, name: str) -> dict:
	"""Submit a draft document from the in-app viewer."""
	doc = frappe.get_doc(doctype, name)
	doc.submit()
	return {"name": doc.name, "docstatus": doc.docstatus}


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

	Without `print_format` we delegate to the integration (its default behaviour).
	With one, we build the PDF from that format and hand it to the same media sender.
	"""
	if not print_format:
		from whatsapp_integration.api.whatsapp.whatsapp import send_document_via_whatsapp

		result = send_document_via_whatsapp(
			doctype, name, phone_number=phone_number or None, message=message or None, sender=sender or None
		)
		return result or {"success": True}

	from frappe.utils import now_datetime
	from frappe.utils.pdf import get_pdf
	from whatsapp_integration.api.files import save_private_pdf
	from whatsapp_integration.api.whatsapp.validators import validate_phone_number, validate_user_permissions
	from whatsapp_integration.api.whatsapp.whatsapp import (
		_finalize_send,
		make_html_pdf_ready,
		normalize_phone_number,
	)
	from whatsapp_integration.service.rest import send_whatsapp_media

	validate_user_permissions(frappe.session.user, "send_message")

	if not phone_number:
		phone_number = resolve_document_phone(doctype, name)
	if not phone_number:
		frappe.throw(_("Please provide a phone number."))
	phone_number = normalize_phone_number(phone_number)
	validate_phone_number(phone_number)

	try:
		html = frappe.get_print(doctype, name, print_format=print_format, no_letterhead=0)
		html = make_html_pdf_ready(html)
		pdf_content = get_pdf(
			html,
			options={
				"load-error-handling": "ignore",
				"load-media-error-handling": "ignore",
				"no-stop-slow-scripts": True,
				"quiet": "",
			},
		)
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Kamil WhatsApp PDF Generation Failed")
		return {
			"success": False,
			"status": "pdf_error",
			"error": _("Could not generate PDF for {0} {1}: {2}").format(doctype, name, str(e)),
		}

	file_name = f"{doctype}_{name}_{now_datetime().strftime('%Y%m%d_%H%M%S')}.pdf"
	file_name = file_name.replace(" ", "_").replace("/", "-")
	file_doc, media_url = save_private_pdf(
		pdf_content, file_name, attached_to_doctype=doctype, attached_to_name=name
	)
	if not file_doc.file_url:
		frappe.throw(_("Failed to generate file URL for the WhatsApp attachment."))

	if not message:
		message = _("Please find attached {0}: {1}").format(doctype, name)

	response = send_whatsapp_media(
		to_number=phone_number,
		message=message,
		media_url=media_url,
		file_name=file_name.replace(".pdf", ""),
		country_name=None,
		sender=sender or None,
		reference_doctype=doctype,
		reference_name=name,
	)

	return _finalize_send(
		response,
		phone_number,
		title="WhatsApp Document Send Failed",
		success_msg=_("Document {0} sent to {1} via WhatsApp.").format(name, phone_number),
		log_context=f"Document: {doctype} {name} ({print_format})",
		notify=0,
		silent=True,
	)


@frappe.whitelist()
def list_whatsapp_senders() -> list:
	"""WhatsApp sender numbers available to the current user (for the sender picker)."""
	from whatsapp_integration.api.whatsapp.whatsapp import get_whatsapp_senders

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
		candidates.append({"label": "This month", "value": _agg_sum(doctype, submitted_month, amount_field), "money": True, "color": "green"})
		candidates.append({"label": "This month (count)", "value": _agg_count(doctype, submitted_month), "money": False, "color": "blue"})

	if meta.has_field("outstanding_amount"):
		f = base + [["docstatus", "=", 1], ["outstanding_amount", ">", 0]]
		candidates.append({"label": "Outstanding", "value": _agg_sum(doctype, f, "outstanding_amount"), "money": True, "color": "amber"})

	if submittable:
		candidates.append({"label": "Drafts", "value": _agg_count(doctype, base + [["docstatus", "=", 0]]), "money": False, "color": "orange"})

	if amount_field and date_field:
		f = period(date_field, year_start) + [["docstatus", "=", 1]]
		candidates.append({"label": "This year", "value": _agg_sum(doctype, f, amount_field), "money": True, "color": "green"})

	if submittable:
		candidates.append({"label": "Submitted", "value": _agg_count(doctype, base + [["docstatus", "=", 1]]), "money": False, "color": "blue"})

	if meta.has_field("disabled"):
		candidates.append({"label": "Active", "value": _agg_count(doctype, base + [["disabled", "=", 0]]), "money": False, "color": "green"})

	candidates.append({"label": "Total records", "value": _agg_count(doctype, base), "money": False, "color": "blue"})

	if meta.has_field("disabled"):
		candidates.append({"label": "Disabled", "value": _agg_count(doctype, base + [["disabled", "=", 1]]), "money": False, "color": "orange"})

	candidates.append({"label": "Added this month", "value": _agg_count(doctype, base + [["creation", ">=", month_start]]), "money": False, "color": "amber"})

	return {"currency": _currency_for(company), "kpis": candidates[:4]}


@frappe.whitelist()
def cancel_document(doctype: str, name: str) -> dict:
	"""Cancel a submitted document (reverses its ledger entries)."""
	doc = frappe.get_doc(doctype, name)
	doc.cancel()
	return {"name": doc.name, "docstatus": doc.docstatus}


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
			fieldtype = (parts[1].split("/")[0] if len(parts) > 1 else "Data") or "Data"
			columns.append({"label": label, "fieldname": frappe.scrub(label), "fieldtype": fieldtype})
		else:
			label = col.get("label") or col.get("fieldname") or ""
			columns.append(
				{
					"label": label,
					"fieldname": col.get("fieldname") or frappe.scrub(label),
					"fieldtype": col.get("fieldtype") or "Data",
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


@frappe.whitelist()
def export_report(report: str, filters: str | dict | None = None, file_format: str = "Excel") -> None:
	"""Stream a query report as .xlsx (or .csv) download."""
	data = run_report(report, filters, limit=100000)
	columns = data.get("columns") or []
	rows = data.get("rows") or []

	matrix = [[c.get("label") or c.get("fieldname") for c in columns]]
	for row in rows:
		matrix.append([("" if row.get(c["fieldname"]) is None else row.get(c["fieldname"])) for c in columns])

	safe_name = (report or "report").replace(" ", "_").replace("/", "-")

	if (file_format or "").lower() == "csv":
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
	}


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
_DOC_TRANSITIONS = {
	"Quotation": [
		("Sales Order", "Sales Order", "erpnext.selling.doctype.quotation.quotation.make_sales_order"),
	],
	"Sales Order": [
		("Delivery Note", "Delivery Note", "erpnext.selling.doctype.sales_order.sales_order.make_delivery_note"),
		("Sales Invoice", "Sales Invoice", "erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice"),
	],
	"Delivery Note": [
		("Sales Invoice", "Sales Invoice", "erpnext.stock.doctype.delivery_note.delivery_note.make_sales_invoice"),
	],
	"Material Request": [
		("Purchase Order", "Purchase Order", "erpnext.stock.doctype.material_request.material_request.make_purchase_order"),
		("Stock Entry", "Stock Entry", "erpnext.stock.doctype.material_request.material_request.make_stock_entry"),
	],
	"Purchase Order": [
		("Purchase Receipt", "Purchase Receipt", "erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_receipt"),
		("Purchase Invoice", "Purchase Invoice", "erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_invoice"),
	],
	"Purchase Receipt": [
		("Purchase Invoice", "Purchase Invoice", "erpnext.stock.doctype.purchase_receipt.purchase_receipt.make_purchase_invoice"),
	],
}


@frappe.whitelist()
def get_doc_transitions(doctype: str) -> list:
	"""Documents that can be created FROM a given doctype (needs create perm on target)."""
	out = []
	for label, target, _method in _DOC_TRANSITIONS.get(doctype, []):
		if frappe.has_permission(target, "create"):
			out.append({"label": label, "target": target})
	return out


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


@frappe.whitelist()
def get_app_links() -> dict:
	"""Optional external app shortcuts shown in the UI (only if installed)."""
	installed = frappe.get_installed_apps() or []
	return {"raven": "/raven" if "raven" in installed else None}
