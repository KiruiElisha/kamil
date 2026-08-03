"""Payment Request driven payments.

Every payment in the app is raised as a Payment Request first, sent to the approver by
email and/or WhatsApp with a link back into the app, and only turns into a Payment Entry
once approved. Approval reuses ERPNext's own ``PaymentRequest.create_payment_entry``,
which builds the entry through ``get_payment_entry`` — that is what allocates the payment
against the reference invoice, so reconciliation happens as part of creating the entry
rather than as a separate step.

Expenses take one extra hop. A Payment Request always needs a reference document
(``validate_reference_document`` throws without one), so a direct expense first books a
Purchase Invoice carrying the chosen expense account, and the Payment Request is raised
against that invoice. The result is proper double entry: the invoice debits the expense
account and credits the payable, the payment entry then settles the payable.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, get_url, nowdate

# Approving a payment is its own responsibility, not a side effect of holding a broad
# accounting role: a bookkeeper who may post entries is not necessarily the person who
# may release money. The dedicated role is created by kamil/setup.py. System Manager
# stays so a site can never end up with nobody able to approve — and so whoever
# administers the site can grant the role in the first place.
PAYMENT_APPROVER_ROLE = "Payment Approver"
APPROVE_ROLES = (PAYMENT_APPROVER_ROLE, "System Manager")


def _can_approve() -> bool:
	return bool(set(frappe.get_roles()) & set(APPROVE_ROLES))


def _require_approver() -> None:
	if not _can_approve():
		frappe.throw(
			_("You are not allowed to approve payments. This needs one of: {0}").format(
				", ".join(APPROVE_ROLES)
			),
			frappe.PermissionError,
		)


#: Which party a payment request is with, per reference doctype.
_BUYING_DOCTYPES = ("Purchase Invoice", "Purchase Order")


def _party_for(ref) -> tuple[str, str | None]:
	"""(party_type, party) for a reference document."""
	if ref.doctype in _BUYING_DOCTYPES:
		return "Supplier", ref.get("supplier")
	return "Customer", ref.get("customer")


def _mode_of_payment_account(mode_of_payment: str | None, company: str | None) -> str | None:
	"""The bank/cash account configured against a Mode of Payment for a company.

	ERPNext's ``get_bank_cash_account`` does resolve an account from a mode of payment,
	but it reads the mode off the *reference invoice* — not off the Payment Request. So
	we look it up here and hand it in explicitly, which is what makes the mode chosen on
	the request actually drive which account the money moves through.
	"""
	if not mode_of_payment or not company:
		return None

	return frappe.db.get_value(
		"Mode of Payment Account",
		{"parent": mode_of_payment, "company": company},
		"default_account",
	)


def payment_settings() -> frappe._dict:
	"""Where payment approvals go, from Kamil Settings.

	One person handles approvals, so the app should not ask for their address on
	every request — the caller may still override it per request.
	"""
	try:
		settings = frappe.get_cached_doc("Kamil Settings")
	except Exception:
		return frappe._dict()

	email = (settings.payment_approver_email or "").strip()
	if not email and settings.payment_approver:
		email = frappe.db.get_value("User", settings.payment_approver, "email") or ""

	return frappe._dict(
		{
			"approver": settings.payment_approver,
			"email": email,
			"phone": (settings.payment_approver_phone or "").strip(),
			"notify_by_email": cint(settings.notify_by_email),
			"notify_by_whatsapp": cint(settings.notify_by_whatsapp),
		}
	)


@frappe.whitelist()
def get_payment_settings() -> dict:
	"""The approval defaults, for the request form and the settings screen."""
	return dict(payment_settings())


def _attach_files(doctype: str, name: str, file_urls) -> list:
	"""Attach already-uploaded files to a document.

	The approver has to see what they are paying for — the supplier's invoice, the
	quote, the delivery note — so the request carries them rather than living in
	somebody's inbox. Frappe allows several File rows to point at one stored file, so
	this attaches without copying anything.
	"""
	if isinstance(file_urls, str):
		try:
			file_urls = frappe.parse_json(file_urls)
		except Exception:
			file_urls = [file_urls]
	if not isinstance(file_urls, list):
		return []

	attached = []
	for url in file_urls:
		url = (url or "").strip()
		if not url:
			continue
		try:
			source = frappe.db.get_value("File", {"file_url": url}, ["file_name", "is_private"], as_dict=True)
			frappe.get_doc(
				{
					"doctype": "File",
					"file_url": url,
					"file_name": (source or {}).get("file_name"),
					"is_private": cint((source or {}).get("is_private")),
					"attached_to_doctype": doctype,
					"attached_to_name": name,
				}
			).insert(ignore_permissions=True)
			attached.append(url)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Kamil: attaching to payment request")
	return attached


def attach_reference_print(name: str) -> dict:
	"""Attach the referenced document's print to the request.

	The approver needs the invoice itself, and asking the requester to download and
	re-upload a PDF the system can produce is busywork. Queued when the queue is up,
	run inline when it is not — either way raising the request still succeeds.
	"""
	from kamil.background import enqueue_or_run

	return enqueue_or_run("kamil.payment_flow.build_reference_print", name=name)


@frappe.whitelist()
def build_reference_print(name: str) -> dict:
	"""Render the reference document to PDF and attach it. Safe to re-run.

	Whitelisted as well as queued: PDF rendering depends on wkhtmltopdf being able to
	fetch the site's own assets, which can fail transiently, and the approver should be
	able to ask for the invoice again rather than being stuck without it.
	"""
	pr = frappe.get_doc("Payment Request", name)
	if not (pr.reference_doctype and pr.reference_name):
		return {"attached": False}

	file_name = f"{pr.reference_name}.pdf".replace(" ", "_").replace("/", "-")
	if frappe.db.exists(
		"File", {"attached_to_doctype": "Payment Request", "attached_to_name": name, "file_name": file_name}
	):
		return {"attached": False, "reason": "already attached"}

	from frappe.utils.pdf import get_pdf

	html = frappe.get_print(pr.reference_doctype, pr.reference_name, no_letterhead=0)
	try:
		content = get_pdf(
			html,
			# Same options the WhatsApp attachment uses, which renders these documents
			# fine on a server that can reach its own assets.
			options={
				"load-error-handling": "ignore",
				"load-media-error-handling": "ignore",
				"no-stop-slow-scripts": True,
				"quiet": "",
			},
		)
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Kamil: rendering the reference print")
		return {"attached": False, "error": str(e)[:200]}

	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": file_name,
			"content": content,
			"is_private": 1,
			"attached_to_doctype": "Payment Request",
			"attached_to_name": name,
		}
	).insert(ignore_permissions=True)
	return {"attached": True, "file_url": file_doc.file_url}


def approval_url(name: str) -> str:
	"""Deep link into the app's approval screen. Requires a login — the route is inside
	the SPA and every action behind it re-checks permissions server-side."""
	return get_url(f"/kamil/payment-approval/{name}")


# ---------------------------------------------------------------------------
# Creating requests
# ---------------------------------------------------------------------------


@frappe.whitelist()
def create_payment_request(
	reference_doctype: str,
	reference_name: str,
	amount: float | str | None = None,
	mode_of_payment: str | None = None,
	bank_account: str | None = None,
	cost_center: str | None = None,
	recipient: str | None = None,
	phone_number: str | None = None,
	subject: str | None = None,
	message: str | None = None,
	attachments: str | list | None = None,
	payment_currency: str | None = None,
	exchange_rate: float | str | None = None,
) -> dict:
	"""Raise a Payment Request against an existing invoice or order.

	`payment_currency` and `exchange_rate` are what the money will actually leave in —
	a USD invoice paid out of a KES account — and are applied when the payment entry is
	built at approval. ERPNext's own `currency` stays the invoice's, read-only, as it
	is everywhere else.
	"""
	if not frappe.has_permission("Payment Request", "create"):
		frappe.throw(_("You are not allowed to raise payment requests."), frappe.PermissionError)
	if not frappe.db.exists(reference_doctype, reference_name):
		frappe.throw(_("{0} {1} does not exist.").format(reference_doctype, reference_name))

	from erpnext.accounts.doctype.payment_request.payment_request import make_payment_request

	ref = frappe.get_doc(reference_doctype, reference_name)
	outstanding = flt(ref.get("outstanding_amount") or ref.get("grand_total"))
	amount = flt(amount) or outstanding
	if amount <= 0:
		frappe.throw(_("Nothing left to pay on {0}.").format(reference_name))
	if amount > outstanding + 0.01:
		frappe.throw(
			_("Amount {0} is more than the {1} outstanding on {2}.").format(amount, outstanding, reference_name)
		)

	# make_payment_request defaults party_type to "Customer" and party to ref.customer,
	# which is wrong for anything on the buying side — pass both explicitly.
	party_type, party = _party_for(ref)

	# submit_doc=0 so we can set our own fields before it goes out for approval.
	pr = make_payment_request(
		dt=reference_doctype,
		dn=reference_name,
		grand_total=amount,
		party_type=party_type,
		party=party,
		mode_of_payment=mode_of_payment or None,
		recipient_id=recipient or None,
		submit_doc=0,
		mute_email=1,
		return_doc=1,
	)

	if mode_of_payment:
		pr.mode_of_payment = mode_of_payment
	if bank_account:
		pr.bank_account = bank_account
	if cost_center:
		pr.cost_center = cost_center
	defaults = payment_settings()
	if not recipient and defaults.email:
		pr.email_to = defaults.email
	if phone_number or defaults.phone:
		pr.phone_number = phone_number or defaults.phone
	if subject:
		pr.subject = subject

	if payment_currency:
		pr.kamil_payment_currency = payment_currency
	if exchange_rate:
		pr.kamil_exchange_rate = flt(exchange_rate)

	# make_payment_request fills `message` with ERPNext's payment-gateway template — a
	# raw Jinja block with a "Make Payment" gateway link. The app mutes that email and
	# sends its own approval mail, so the template is never rendered and would only
	# show up as markup on the approval screen. Replace it with a plain sentence.
	pr.message = message or _("Payment of {0} requested against {1} {2}.").format(
		frappe.utils.fmt_money(amount, currency=pr.currency or None), _(reference_doctype), reference_name
	)

	pr.mute_email = 1  # we do our own sending, so ERPNext must not also email on submit
	pr.flags.ignore_permissions = True
	pr.save()
	pr.submit()

	attached = _attach_files("Payment Request", pr.name, attachments)
	attach_reference_print(pr.name)

	return {
		"name": pr.name,
		"status": pr.status,
		"grand_total": flt(pr.grand_total),
		"attachments": attached,
	}


@frappe.whitelist()
def create_expense_payment_request(
	supplier: str,
	expense_account: str,
	amount: float | str,
	company: str | None = None,
	description: str | None = None,
	mode_of_payment: str | None = None,
	cost_center: str | None = None,
	posting_date: str | None = None,
	recipient: str | None = None,
	phone_number: str | None = None,
	attachments: str | list | None = None,
) -> dict:
	"""Book a direct expense and raise a Payment Request to pay it.

	Creates a Purchase Invoice with a single description-only line carrying
	``expense_account`` (ERPNext's way of booking an expense with no Item master), then
	raises the Payment Request against that invoice.
	"""
	if not frappe.has_permission("Payment Request", "create"):
		frappe.throw(_("You are not allowed to raise payment requests."), frappe.PermissionError)
	if not frappe.has_permission("Purchase Invoice", "create"):
		frappe.throw(_("You are not allowed to book expenses."), frappe.PermissionError)

	amount = flt(amount)
	if amount <= 0:
		frappe.throw(_("Expense amount must be greater than zero."))

	from kamil.api import _resolve_company

	company = _resolve_company(company)
	if not company:
		frappe.throw(_("No company to book this expense against."))

	account_company = frappe.db.get_value("Account", expense_account, "company")
	if account_company and account_company != company:
		frappe.throw(_("Account {0} does not belong to {1}.").format(expense_account, company))

	description = (description or "").strip() or f"Expense — {expense_account}"

	invoice = frappe.get_doc(
		{
			"doctype": "Purchase Invoice",
			"company": company,
			"supplier": supplier,
			"posting_date": posting_date or nowdate(),
			"bill_date": posting_date or nowdate(),
			"items": [
				{
					"item_name": description[:140],
					"description": description,
					"qty": 1,
					"rate": amount,
					"expense_account": expense_account,
					"cost_center": cost_center or None,
				}
			],
		}
	)
	invoice.flags.ignore_permissions = True
	invoice.insert()
	invoice.submit()

	request = create_payment_request(
		reference_doctype="Purchase Invoice",
		reference_name=invoice.name,
		amount=amount,
		mode_of_payment=mode_of_payment,
		cost_center=cost_center,
		recipient=recipient,
		phone_number=phone_number,
		subject=f"Expense payment — {description[:80]}",
		message=description,
		attachments=attachments,
	)

	# The paperwork belongs on the invoice as well as on the request.
	_attach_files("Purchase Invoice", invoice.name, attachments)

	# Mark it as an expense so the app (and the desk) can tell the two flows apart.
	frappe.db.set_value(
		"Payment Request",
		request["name"],
		{"kamil_is_expense": 1, "kamil_expense_account": expense_account},
		update_modified=False,
	)

	request["purchase_invoice"] = invoice.name
	request["expense_account"] = expense_account
	return request


def clear_gateway_messages() -> dict:
	"""Strip ERPNext's payment-gateway template from existing Payment Requests.

	Requests raised before this was fixed carry the raw Jinja block, which the app
	shows verbatim on the approval screen. The message is presentational — the app
	sends its own mail — so replacing it changes nothing about the payment itself.
	Safe to re-run: only rows still holding the template are touched.
	"""
	# Two templates land here: ERPNext's own dummy message (raw Jinja with a "Make
	# Payment" gateway link) and whatever a Payment Gateway Account carries. Both point
	# at a gateway this app does not use.
	rows = frappe.get_all(
		"Payment Request",
		or_filters=[
			["message", "like", "%Requesting payment against%"],
			["message", "like", "%Make Payment%"],
			["message", "like", "%click on the link below%"],
		],
		fields=["name", "reference_doctype", "reference_name", "grand_total", "currency"],
		limit_page_length=0,
	)
	for row in rows:
		frappe.db.set_value(
			"Payment Request",
			row.name,
			"message",
			_("Payment of {0} requested against {1} {2}.").format(
				frappe.utils.fmt_money(flt(row.grand_total), currency=row.currency or None),
				_(row.reference_doctype or ""),
				row.reference_name or "",
			),
			update_modified=False,
		)
	frappe.db.commit()
	return {"cleared": len(rows)}


# ---------------------------------------------------------------------------
# Internal transfers
# ---------------------------------------------------------------------------
#
# Moving money between the company's own accounts has no party and no invoice, so it
# cannot be a Payment Request — ERPNext requires a reference document. It is instead
# raised as a *draft* Payment Entry of type "Internal Transfer", which the same
# approvers release. Nothing hits the ledger until it is submitted, so the draft plays
# exactly the role the payment request plays for the other flows.


def transfer_approval_url(name: str) -> str:
	"""Deep link into the approval screen for a drafted internal transfer."""
	return get_url(f"/kamil/payment-approval/{name}?type=transfer")


def _account_currency(account: str) -> str | None:
	return frappe.db.get_value("Account", account, "account_currency")


@frappe.whitelist()
def create_internal_transfer(
	paid_from: str,
	paid_to: str,
	amount: float | str,
	company: str | None = None,
	mode_of_payment: str | None = None,
	reference_no: str | None = None,
	remarks: str | None = None,
	posting_date: str | None = None,
) -> dict:
	"""Draft an Internal Transfer payment entry for approval.

	Both accounts must belong to the same company and must not be group accounts —
	otherwise the entry could not be submitted once approved, and the request would
	sit in the approver's queue only to fail on release.
	"""
	if not frappe.has_permission("Payment Entry", "create"):
		frappe.throw(_("You are not allowed to raise payments."), frappe.PermissionError)

	amount = flt(amount)
	if amount <= 0:
		frappe.throw(_("Transfer amount must be greater than zero."))
	if not paid_from or not paid_to:
		frappe.throw(_("Pick the account to move money from and the account to move it to."))
	if paid_from == paid_to:
		frappe.throw(_("The two accounts must be different."))

	from kamil.api import _resolve_company

	company = _resolve_company(company)
	if not company:
		frappe.throw(_("No company to raise this transfer for."))

	for account in (paid_from, paid_to):
		row = frappe.db.get_value("Account", account, ["company", "is_group"], as_dict=True)
		if not row:
			frappe.throw(_("Account {0} does not exist.").format(account))
		if row.company != company:
			frappe.throw(_("Account {0} does not belong to {1}.").format(account, company))
		if row.is_group:
			frappe.throw(_("Account {0} is a group and cannot hold a payment.").format(account))

	entry = frappe.get_doc(
		{
			"doctype": "Payment Entry",
			"payment_type": "Internal Transfer",
			"company": company,
			"posting_date": posting_date or nowdate(),
			"paid_from": paid_from,
			"paid_to": paid_to,
			"paid_amount": amount,
			"received_amount": amount,
			"mode_of_payment": mode_of_payment or None,
			"reference_no": reference_no or None,
			"reference_date": posting_date or nowdate() if reference_no else None,
			"remarks": remarks or None,
		}
	)
	# Currency conversion between two different account currencies needs rates the app
	# does not ask for; keep the app to same-currency transfers and say so plainly.
	if _account_currency(paid_from) != _account_currency(paid_to):
		frappe.throw(_("Transfers between accounts in different currencies must be done on the desk."))

	entry.flags.ignore_permissions = True
	entry.insert()  # left as a draft — approval submits it

	return {
		"name": entry.name,
		"doctype": "Payment Entry",
		"paid_amount": flt(entry.paid_amount),
		"status": "Draft",
		"link": transfer_approval_url(entry.name),
	}


@frappe.whitelist()
def get_internal_transfer(name: str) -> dict:
	"""A drafted internal transfer, for the approval screen."""
	entry = frappe.get_doc("Payment Entry", name)
	entry.check_permission("read")

	if entry.payment_type != "Internal Transfer":
		frappe.throw(_("{0} is not an internal transfer.").format(name))

	return {
		"name": entry.name,
		"doctype": "Payment Entry",
		"is_transfer": True,
		"company": entry.company,
		"posting_date": str(entry.posting_date),
		"paid_from": entry.paid_from,
		"paid_to": entry.paid_to,
		"paid_amount": flt(entry.paid_amount),
		"currency": entry.paid_from_account_currency,
		"mode_of_payment": entry.mode_of_payment,
		"reference_no": entry.reference_no,
		"remarks": entry.remarks,
		"docstatus": entry.docstatus,
		"status": {0: "Draft", 1: "Paid", 2: "Cancelled"}.get(entry.docstatus, "Draft"),
		"can_approve": _can_approve(),
	}


@frappe.whitelist()
def approve_internal_transfer(name: str, mode_of_payment: str | None = None) -> dict:
	"""Release a drafted internal transfer — this is what moves the money."""
	_require_approver()

	entry = frappe.get_doc("Payment Entry", name)
	if entry.payment_type != "Internal Transfer":
		frappe.throw(_("{0} is not an internal transfer.").format(name))
	if entry.docstatus == 1:
		frappe.throw(_("{0} has already been paid.").format(name))
	if entry.docstatus == 2:
		frappe.throw(_("{0} was cancelled.").format(name))

	if mode_of_payment and mode_of_payment != entry.mode_of_payment:
		entry.mode_of_payment = mode_of_payment

	entry.flags.ignore_permissions = True
	entry.submit()
	entry.add_comment("Comment", _("Internal transfer approved in the Kamil app by {0}.").format(frappe.session.user))

	return {
		"name": entry.name,
		"payment_entry": entry.name,
		"paid_amount": flt(entry.paid_amount),
		"status": "Paid",
	}


@frappe.whitelist()
def reject_internal_transfer(name: str, reason: str) -> dict:
	"""Reject a drafted transfer, recording why.

	A draft has posted nothing, so there is no entry to reverse: the rejection is
	written onto the draft, which is then cancelled by submitting nothing — Frappe
	cannot cancel a draft, so the request is deleted instead and the reason returned
	to the caller (and to whoever raised it, via the approval screen).
	"""
	_require_approver()

	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("Please give a reason for rejecting this transfer."))

	entry = frappe.get_doc("Payment Entry", name)
	if entry.payment_type != "Internal Transfer":
		frappe.throw(_("{0} is not an internal transfer.").format(name))
	if entry.docstatus == 1:
		frappe.throw(_("{0} has already been paid and cannot be rejected.").format(name))
	if entry.docstatus == 2:
		return {"name": name, "status": "Cancelled", "reason": reason}

	summary = {
		"name": entry.name,
		"status": "Rejected",
		"reason": reason,
		"paid_from": entry.paid_from,
		"paid_to": entry.paid_to,
		"paid_amount": flt(entry.paid_amount),
	}
	frappe.delete_doc("Payment Entry", name, ignore_permissions=True, delete_permanently=False)
	return summary


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------


@frappe.whitelist()
def send_payment_request(
	name: str,
	via_email: int | str = 1,
	via_whatsapp: int | str = 0,
	recipient: str | None = None,
	phone_number: str | None = None,
	sender: str | None = None,
) -> dict:
	"""Send a payment request for approval by email and/or WhatsApp.

	Each channel reports its own outcome; one failing does not stop the other.
	"""
	pr = frappe.get_doc("Payment Request", name)
	if not pr.has_permission("read"):
		frappe.throw(_("Not permitted."), frappe.PermissionError)

	defaults = payment_settings()
	recipient = (recipient or "").strip() or defaults.email or None
	phone_number = (phone_number or "").strip() or defaults.phone or None

	link = approval_url(name)
	results = {"name": name, "link": link, "email": None, "whatsapp": None}

	if frappe.utils.cint(via_email):
		results["email"] = _send_email(pr, recipient, link)
	if frappe.utils.cint(via_whatsapp):
		results["whatsapp"] = _send_whatsapp(pr, phone_number, sender, link)

	return results


def _approval_body(pr, link: str) -> str:
	currency = pr.currency or ""
	amount = frappe.utils.fmt_money(pr.grand_total, currency=currency)
	return f"""<p>A payment needs your approval.</p>
<table cellpadding="6">
  <tr><td><b>Request</b></td><td>{frappe.utils.escape_html(pr.name)}</td></tr>
  <tr><td><b>Party</b></td><td>{frappe.utils.escape_html(pr.party_name or pr.party or "")}</td></tr>
  <tr><td><b>Amount</b></td><td>{amount}</td></tr>
  <tr><td><b>Against</b></td><td>{frappe.utils.escape_html(f"{pr.reference_doctype} {pr.reference_name}")}</td></tr>
  <tr><td><b>Mode</b></td><td>{frappe.utils.escape_html(pr.mode_of_payment or "—")}</td></tr>
</table>
<p><a href="{link}">Review and approve this payment</a></p>
<p style="color:#888;font-size:12px">You will be asked to sign in first. Approving creates the
payment entry and reconciles it against {frappe.utils.escape_html(pr.reference_name or "the invoice")}.</p>"""


def _send_email(pr, recipient: str | None, link: str) -> dict:
	recipient = (recipient or pr.email_to or "").strip()
	if not recipient:
		return {"sent": False, "error": _("No recipient email address.")}

	try:
		frappe.sendmail(
			recipients=[recipient],
			subject=pr.subject or _("Payment approval needed: {0}").format(pr.name),
			message=_approval_body(pr, link),
			reference_doctype="Payment Request",
			reference_name=pr.name,
			now=True,
		)
		return {"sent": True, "to": recipient}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Kamil Payment Request email failed")
		return {"sent": False, "error": str(e)}


def _send_whatsapp(pr, phone_number: str | None, sender: str | None, link: str) -> dict:
	"""Send the approval request, with the document being paid for attached.

	An approver deciding on a payment wants the invoice in front of them, so the
	reference document goes out as a PDF with the request as its caption. If the PDF
	cannot be built the message still goes as text — a missing attachment is no reason
	for the approver to hear nothing.
	"""
	if "whatsapp_integration" not in (frappe.get_installed_apps() or []):
		return {"sent": False, "error": _("WhatsApp integration is not installed.")}

	phone_number = (phone_number or pr.phone_number or "").strip()
	if not phone_number:
		# Fall back to whatever the party master has on file.
		from kamil.api import resolve_document_phone

		phone_number = resolve_document_phone("Payment Request", pr.name) or ""
	if not phone_number:
		return {"sent": False, "error": _("No phone number to send to.")}

	amount = frappe.utils.fmt_money(pr.grand_total, currency=pr.currency or "")
	text = _("Payment approval needed: {0} for {1} ({2}). Approve here: {3}").format(
		pr.name, pr.party_name or pr.party or "", amount, link
	)

	if pr.reference_doctype and pr.reference_name:
		try:
			from kamil.whatsapp import send_document

			result = send_document(
				pr.reference_doctype,
				pr.reference_name,
				phone_number=phone_number,
				message=text,
				sender=sender or None,
			)
			if result.get("success"):
				return {"sent": True, "to": result.get("phone_number") or phone_number, "attached": True}
			frappe.log_error(
				f"{pr.name}: sending {pr.reference_doctype} {pr.reference_name} failed "
				f"({result.get('error')}); falling back to text",
				"Kamil Payment Request WhatsApp",
			)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Kamil Payment Request WhatsApp attachment")

	return _whatsapp_text(phone_number, text, sender, "Kamil Payment Request WhatsApp failed")


def _whatsapp_text(phone_number: str, text: str, sender: str | None, log_title: str) -> dict:
	"""Send an approval message through the app's own WhatsApp transport, which wakes
	the sleeping gateway first and retries on timeouts (see kamil/whatsapp.py)."""
	try:
		from kamil.whatsapp import send_text

		result = send_text(phone_number, text, sender=sender or None)
		return {
			"sent": bool(result.get("success")),
			"to": result.get("phone_number") or phone_number,
			"error": result.get("error"),
		}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), log_title)
		return {"sent": False, "error": str(e)}


@frappe.whitelist()
def send_internal_transfer(
	name: str,
	via_email: int | str = 1,
	via_whatsapp: int | str = 0,
	recipient: str | None = None,
	phone_number: str | None = None,
	sender: str | None = None,
) -> dict:
	"""Send a drafted internal transfer for approval, like send_payment_request does."""
	entry = frappe.get_doc("Payment Entry", name)
	entry.check_permission("read")
	if entry.payment_type != "Internal Transfer":
		frappe.throw(_("{0} is not an internal transfer.").format(name))

	defaults = payment_settings()
	recipient = (recipient or "").strip() or defaults.email or None
	phone_number = (phone_number or "").strip() or defaults.phone or None

	link = transfer_approval_url(name)
	results = {"name": name, "link": link, "email": None, "whatsapp": None}
	amount = frappe.utils.fmt_money(entry.paid_amount, currency=entry.paid_from_account_currency or "")

	if frappe.utils.cint(via_email):
		recipient = (recipient or "").strip()
		if not recipient:
			results["email"] = {"sent": False, "error": _("No recipient email address.")}
		else:
			body = f"""<p>An internal transfer needs your approval.</p>
<table cellpadding="6">
  <tr><td><b>Reference</b></td><td>{frappe.utils.escape_html(entry.name)}</td></tr>
  <tr><td><b>From</b></td><td>{frappe.utils.escape_html(entry.paid_from)}</td></tr>
  <tr><td><b>To</b></td><td>{frappe.utils.escape_html(entry.paid_to)}</td></tr>
  <tr><td><b>Amount</b></td><td>{amount}</td></tr>
</table>
<p><a href="{link}">Review and approve this transfer</a></p>
<p style="color:#888;font-size:12px">Nothing has moved yet — the transfer is a draft until you approve it.</p>"""
			try:
				frappe.sendmail(
					recipients=[recipient],
					subject=_("Internal transfer approval needed: {0}").format(entry.name),
					message=body,
					reference_doctype="Payment Entry",
					reference_name=entry.name,
					now=True,
				)
				results["email"] = {"sent": True, "to": recipient}
			except Exception as e:
				frappe.log_error(frappe.get_traceback(), "Kamil Internal Transfer email failed")
				results["email"] = {"sent": False, "error": str(e)}

	if frappe.utils.cint(via_whatsapp):
		phone_number = (phone_number or "").strip()
		if not phone_number:
			results["whatsapp"] = {"sent": False, "error": _("No phone number to send to.")}
		else:
			text = _("Internal transfer approval needed: {0} — {1} from {2} to {3}. Approve here: {4}").format(
				entry.name, amount, entry.paid_from, entry.paid_to, link
			)
			results["whatsapp"] = _whatsapp_text(
				phone_number, text, sender, "Kamil Internal Transfer WhatsApp failed"
			)

	return results


# ---------------------------------------------------------------------------
# Approval
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_payment_request(name: str) -> dict:
	"""Everything the approval screen needs about one request."""
	pr = frappe.get_doc("Payment Request", name)
	if not pr.has_permission("read"):
		frappe.throw(_("Not permitted."), frappe.PermissionError)

	existing = frappe.get_all(
		"Payment Entry Reference",
		filters={"reference_doctype": pr.reference_doctype, "reference_name": pr.reference_name, "docstatus": 1},
		fields=["parent"],
		limit=5,
	)

	outstanding = None
	if pr.reference_doctype and pr.reference_name:
		outstanding = frappe.db.get_value(pr.reference_doctype, pr.reference_name, "outstanding_amount")

	return {
		"name": pr.name,
		"status": pr.status,
		"docstatus": pr.docstatus,
		"party": pr.party,
		"party_name": pr.party_name,
		"party_type": pr.party_type,
		"grand_total": flt(pr.grand_total),
		"currency": pr.currency,
		"mode_of_payment": pr.mode_of_payment,
		"cost_center": pr.cost_center,
		"reference_doctype": pr.reference_doctype,
		"reference_name": pr.reference_name,
		"outstanding_amount": flt(outstanding) if outstanding is not None else None,
		"payment_request_type": pr.payment_request_type,
		"is_expense": bool(pr.get("kamil_is_expense")),
		"expense_account": pr.get("kamil_expense_account"),
		"approved_by": pr.get("kamil_approved_by"),
		"approved_on": str(pr.get("kamil_approved_on") or "") or None,
		"rejection_reason": pr.get("kamil_rejection_reason"),
		"subject": pr.subject,
		"message": pr.message,
		"email_to": pr.email_to,
		"phone_number": pr.phone_number,
		"payment_entries": [row.parent for row in existing],
		"reference_print_attached": bool(
			frappe.db.exists(
				"File",
				{
					"attached_to_doctype": "Payment Request",
					"attached_to_name": pr.name,
					"file_name": ("like", f"%{pr.reference_name}%"),
				},
			)
		)
		if pr.reference_name
		else False,
		"payment_currency": pr.get("kamil_payment_currency"),
		"exchange_rate": flt(pr.get("kamil_exchange_rate")) or None,
		"payment_account": pr.payment_account or _mode_of_payment_account(pr.mode_of_payment, pr.company),
		"payment_account_currency": frappe.db.get_value(
			"Account",
			pr.payment_account or _mode_of_payment_account(pr.mode_of_payment, pr.company),
			"account_currency",
		)
		if (pr.payment_account or pr.mode_of_payment)
		else None,
		"attachments": [
			{"file_name": f.file_name, "file_url": f.file_url}
			for f in frappe.get_all(
				"File",
				filters={"attached_to_doctype": "Payment Request", "attached_to_name": pr.name},
				fields=["file_name", "file_url"],
			)
		],
		"can_approve": _can_approve(),
	}


@frappe.whitelist()
def approve_payment_request(name: str, mode_of_payment: str | None = None) -> dict:
	"""Approve a request: create the Payment Entry and reconcile it in one step.

	``create_payment_entry`` goes through ERPNext's ``get_payment_entry``, which fills in
	the reference row for the invoice — so the entry lands already allocated against it.
	"""
	_require_approver()

	pr = frappe.get_doc("Payment Request", name)

	if pr.docstatus != 1:
		frappe.throw(_("Only a submitted payment request can be approved."))
	if pr.status in ("Paid", "Payment Ordered"):
		frappe.throw(_("{0} is already {1}.").format(name, pr.status))
	if pr.status == "Cancelled":
		frappe.throw(_("{0} was cancelled.").format(name))

	if mode_of_payment and mode_of_payment != pr.mode_of_payment:
		pr.db_set("mode_of_payment", mode_of_payment, update_modified=False)
		pr.reload()

	# Route the money through the account configured for the chosen mode of payment.
	# create_payment_entry passes `payment_account` straight to get_payment_entry as the
	# bank account, so setting it here is enough — ERPNext still derives the currencies
	# and amounts from that account itself.
	if not pr.payment_account:
		account = _mode_of_payment_account(pr.mode_of_payment, pr.company)
		if account:
			pr.payment_account = account

	# Built unsubmitted so the requested rate can be applied before it posts — ERPNext
	# otherwise takes the rate off the reference document.
	entry = pr.create_payment_entry(submit=False)
	rate = flt(pr.get("kamil_exchange_rate"))
	if rate:
		company_currency = frappe.get_cached_value("Company", pr.company, "default_currency")
		if entry.paid_from_account_currency != company_currency:
			entry.source_exchange_rate = rate
		if entry.paid_to_account_currency != company_currency:
			entry.target_exchange_rate = rate
		entry.setup_party_account_field()
		entry.set_missing_values()
		entry.set_amounts()
	entry.flags.ignore_permissions = True
	entry.save()
	entry.submit()

	pr.db_set(
		{
			"kamil_approved_by": frappe.session.user,
			"kamil_approved_on": frappe.utils.now_datetime(),
			"kamil_rejection_reason": None,
		},
		update_modified=False,
	)

	pr.add_comment("Comment", _("Approved in the Kamil app by {0}.").format(frappe.session.user))

	allocated = sum(flt(r.allocated_amount) for r in (entry.references or []))
	return {
		"name": pr.name,
		"payment_entry": entry.name,
		"paid_amount": flt(entry.paid_amount),
		"allocated_amount": allocated,
		"reconciled": bool(entry.references),
		"status": frappe.db.get_value("Payment Request", pr.name, "status"),
	}


@frappe.whitelist()
def reject_payment_request(name: str, reason: str) -> dict:
	"""Reject a request, recording why. The request is cancelled so it cannot be paid."""
	_require_approver()

	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("Please give a reason for rejecting this payment."))

	pr = frappe.get_doc("Payment Request", name)
	if pr.status in ("Paid", "Payment Ordered"):
		frappe.throw(_("{0} is already {1} and cannot be rejected.").format(name, pr.status))

	pr.db_set(
		{
			"kamil_rejection_reason": reason,
			"kamil_approved_by": None,
			"kamil_approved_on": None,
		},
		update_modified=False,
	)
	if pr.docstatus == 1:
		pr.cancel()

	pr.add_comment("Comment", _("Rejected in the Kamil app by {0}: {1}").format(frappe.session.user, reason))

	return {"name": pr.name, "status": frappe.db.get_value("Payment Request", pr.name, "status"), "reason": reason}


@frappe.whitelist()
def list_payment_approvers() -> list:
	"""Users who could actually approve a payment, for the approver picker.

	Sending the request to somebody without an approving role wastes everyone's time —
	they would open the link only to be told they are not allowed. So the list is the
	holders of APPROVE_ROLES, not every user on the site.
	"""
	if not frappe.has_permission("User", "read"):
		return []

	names = frappe.get_all(
		"Has Role",
		filters={"role": ("in", list(APPROVE_ROLES)), "parenttype": "User"},
		pluck="parent",
		distinct=True,
	)
	if not names:
		return []

	# A list of conditions, not a dict: `name` is constrained twice, and a dict would
	# silently keep only the last of the two.
	rows = frappe.get_all(
		"User",
		filters=[
			["name", "in", names],
			["name", "not in", ["Administrator", "Guest"]],
			["enabled", "=", 1],
			["user_type", "=", "System User"],
		],
		fields=["name", "full_name", "email"],
		order_by="full_name asc",
	)

	return [
		{
			"label": f"{r.full_name} ({r.email or r.name})" if r.full_name else (r.email or r.name),
			"value": r.email or r.name,
		}
		for r in rows
	]


@frappe.whitelist()
def list_payable_documents(reference_doctype: str = "Purchase Invoice") -> list:
	"""Submitted invoices with something still outstanding, for the request form."""
	if not frappe.has_permission(reference_doctype, "read"):
		return []

	party_field = "supplier" if reference_doctype.startswith("Purchase") else "customer"
	rows = frappe.get_list(
		reference_doctype,
		filters={"docstatus": 1, "outstanding_amount": (">", 0)},
		fields=["name", party_field, "outstanding_amount", "currency", "company"],
		# Newest first: the invoice somebody wants to pay is almost always a recent one,
		# and creation breaks ties within a posting date.
		order_by="posting_date desc, creation desc",
		limit_page_length=100,
	)
	return [
		{
			"label": f"{r.name} — {r.get(party_field)} ({flt(r.outstanding_amount):,.2f})",
			"value": r.name,
			"party": r.get(party_field),
			"outstanding": flt(r.outstanding_amount),
			"currency": r.currency,
			"company": r.company,
		}
		for r in rows
	]
