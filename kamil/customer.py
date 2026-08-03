"""Customer KYC verification.

Verification is not a step somebody performs — it is a statement about the paperwork on
file. So the status is derived: once every required document is attached the customer is
Verified, and approving through the workflow verifies it too (an approver has, by
definition, looked at it). Nobody has to remember to flip a field.

The status field itself is a site customisation (`custom_verfication_status`), so
everything here is skipped on a site that does not have it.
"""

import frappe
from frappe import _

STATUS_FIELD = "custom_verfication_status"

# The paperwork a customer needs on file to count as verified. Only the documents that
# actually exist on the site are required — a site without CR12 is not held back by it.
KYC_DOCUMENT_FIELDS = (
	"kamil_license_file",
	"kamil_certificate_of_incorporation",
	"kamil_cr12",
)

VERIFIED = "Verified"
PENDING = "Pending"


def _status_options(meta) -> list:
	field = meta.get_field(STATUS_FIELD)
	if not field or not field.options:
		return []
	return [o.strip() for o in field.options.split("\n") if o.strip()]


def required_documents(meta) -> list:
	return [f for f in KYC_DOCUMENT_FIELDS if meta.has_field(f)]


def missing_documents(doc) -> list:
	"""Which KYC documents are still not attached."""
	return [f for f in required_documents(doc.meta) if not doc.get(f)]


def set_verification_status(doc, method=None) -> None:
	"""Keep the KYC status honest about the paperwork on file.

	Verified means the documents are there — nothing else. Approval no longer implies
	it (an approver signs off on the customer, not on paperwork that may never have
	been uploaded), and a status set to Verified by hand while documents are missing is
	refused rather than quietly saved.
	"""
	if not doc.meta.has_field(STATUS_FIELD):
		return

	options = _status_options(doc.meta)
	if VERIFIED not in options:
		return

	current = (doc.get(STATUS_FIELD) or "").strip()
	missing = missing_documents(doc)

	if current == VERIFIED and missing:
		labels = ", ".join(doc.meta.get_label(f) for f in missing)
		frappe.throw(
			frappe._("{0} cannot be marked as {1} until these are uploaded: {2}").format(
				doc.name or doc.customer_name or _("This customer"), VERIFIED, labels
			)
		)

	if current and current not in (PENDING, VERIFIED, ""):
		return  # a deliberate state this code has no business overriding

	if not missing and required_documents(doc.meta):
		doc.set(STATUS_FIELD, VERIFIED)
	elif PENDING in options and current != PENDING:
		doc.set(STATUS_FIELD, PENDING)


@frappe.whitelist()
def get_kyc_status(customer: str) -> dict:
	"""What is on file for a customer and what is still missing."""
	doc = frappe.get_doc("Customer", customer)
	doc.check_permission("read")

	if not doc.meta.has_field(STATUS_FIELD):
		return {"supported": False}

	missing = missing_documents(doc)
	return {
		"supported": True,
		"status": doc.get(STATUS_FIELD),
		"verified": (doc.get(STATUS_FIELD) or "") == VERIFIED,
		"workflow_state": doc.get("workflow_state"),
		"missing_documents": [
			{"fieldname": f, "label": frappe.get_meta("Customer").get_label(f)} for f in missing
		],
	}

def submit_for_approval(doc, method=None) -> None:
	"""A new customer goes straight into the approval queue.

	There is no draft stage anybody works in — the salesperson fills the form and it is
	raised for approval on save — so the workflow's first state is set here rather than
	waiting for somebody to press a button that only ever had one option.
	"""
	if not doc.meta.has_field("workflow_state"):
		return
	if doc.get("workflow_state"):
		return

	from frappe.model.workflow import get_workflow_name

	if not get_workflow_name("Customer"):
		return
	doc.workflow_state = "Pending Approval"


# ---------------------------------------------------------------------------
# Chasing unverified customers
# ---------------------------------------------------------------------------

STALE_AFTER_DAYS = 30


def notify_pending_verification() -> None:
	"""Daily: flag customers whose paperwork has been outstanding for a month.

	Sent as a notification to whoever approves payments (Kamil Settings) and to every
	System Manager, because an unverified customer that keeps trading is a compliance
	problem rather than a data-entry one.
	"""
	if not frappe.db.exists("DocType", "Customer"):
		return

	meta = frappe.get_meta("Customer")
	if not meta.has_field(STATUS_FIELD):
		return

	cutoff = frappe.utils.add_days(frappe.utils.nowdate(), -STALE_AFTER_DAYS)
	stale = frappe.get_all(
		"Customer",
		filters={STATUS_FIELD: ("!=", VERIFIED), "creation": ("<", cutoff), "disabled": 0},
		fields=["name", "customer_name", "creation"],
		limit_page_length=0,
	)
	if not stale:
		return

	recipients = set(frappe.get_all("Has Role", filters={"role": "System Manager", "parenttype": "User"}, pluck="parent"))
	try:
		from kamil.payment_flow import payment_settings

		approver = payment_settings().approver
		if approver:
			recipients.add(approver)
	except Exception:
		pass
	recipients = {r for r in recipients if r not in ("Administrator", "Guest")}
	if not recipients:
		return

	subject = _("{0} customers have been unverified for over {1} days").format(len(stale), STALE_AFTER_DAYS)
	body = "<br>".join(
		f"{c.customer_name or c.name} — on file since {frappe.utils.formatdate(c.creation)}" for c in stale[:20]
	)
	if len(stale) > 20:
		body += f"<br>… and {len(stale) - 20} more"

	from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

	for user in recipients:
		enqueue_create_notification(
			user,
			{
				"type": "Alert",
				"document_type": "Customer",
				"document_name": stale[0].name,
				"subject": subject,
				"email_content": body,
				"from_user": frappe.session.user,
			},
		)
