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
from frappe.utils import flt, get_url, nowdate

APPROVE_ROLES = ("Accounts Manager", "Accounts User", "System Manager")


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
) -> dict:
	"""Raise a Payment Request against an existing invoice or order."""
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
	if phone_number:
		pr.phone_number = phone_number
	if subject:
		pr.subject = subject
	if message:
		pr.message = message

	pr.mute_email = 1  # we do our own sending, so ERPNext must not also email on submit
	pr.flags.ignore_permissions = True
	pr.save()
	pr.submit()

	return {"name": pr.name, "status": pr.status, "grand_total": flt(pr.grand_total)}


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
	)

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

	try:
		from whatsapp_integration.service.rest import send_whatsapp_message

		response = send_whatsapp_message(
			to_number=phone_number,
			message=text,
			sender=sender or None,
			reference_doctype="Payment Request",
			reference_name=pr.name,
		)
		# The integration signals failure either with an "error" key or success=False.
		error = None
		if not response:
			error = _("WhatsApp send failed.")
		elif isinstance(response, dict):
			if response.get("error"):
				error = str(response["error"])
			elif response.get("success") is False:
				error = str(response.get("message") or _("WhatsApp send failed."))

		return {"sent": not error, "to": phone_number, "error": error}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Kamil Payment Request WhatsApp failed")
		return {"sent": False, "error": str(e)}


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

	entry = pr.create_payment_entry(submit=True)

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
def list_payable_documents(reference_doctype: str = "Purchase Invoice") -> list:
	"""Submitted invoices with something still outstanding, for the request form."""
	if not frappe.has_permission(reference_doctype, "read"):
		return []

	party_field = "supplier" if reference_doctype.startswith("Purchase") else "customer"
	rows = frappe.get_list(
		reference_doctype,
		filters={"docstatus": 1, "outstanding_amount": (">", 0)},
		fields=["name", party_field, "outstanding_amount", "currency", "company"],
		order_by="posting_date desc",
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
