"""Customer KYC verification.

Verification is not a step somebody performs — it is a statement about the paperwork on
file. So the status is derived: once every required document is attached the customer is
Verified, and approving through the workflow verifies it too (an approver has, by
definition, looked at it). Nobody has to remember to flip a field.

The status field itself is a site customisation (`custom_verfication_status`), so
everything here is skipped on a site that does not have it.
"""

import frappe

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
	"""Derive the KYC status from the documents on file and the approval state.

	Runs on validate, so it applies however the customer is saved — the app, the desk
	or an import. A status somebody set by hand to something other than Pending or
	Verified (a site may have "Rejected", "On Hold" …) is left alone.
	"""
	if not doc.meta.has_field(STATUS_FIELD):
		return

	options = _status_options(doc.meta)
	if VERIFIED not in options:
		return

	current = (doc.get(STATUS_FIELD) or "").strip()
	if current and current not in (PENDING, VERIFIED, ""):
		return  # a deliberate state this code has no business overriding

	approved = (doc.get("workflow_state") or "").strip() == "Approved"
	complete = not missing_documents(doc)

	if approved or complete:
		doc.set(STATUS_FIELD, VERIFIED)
	elif PENDING in options and not current:
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
