"""Schema this app needs on top of stock ERPNext: custom fields and workflows.

Everything here is idempotent and runs from ``after_install`` / ``after_migrate``, so
the app can be installed on a fresh site or an existing one without manual setup.

Deliberately NOT re-created here, because ERPNext already ships them:
    Customer.tax_id, Customer.customer_primary_address, Customer.primary_address
    Payment Request.mode_of_payment, .cost_center, .bank_account, .email_to, .phone_number
"""

import frappe
from frappe import _

# ---------------------------------------------------------------------------
# Custom fields
# ---------------------------------------------------------------------------

CUSTOM_FIELDS = {
	"Customer": [
		{
			"fieldname": "kamil_compliance_section",
			"label": "Statutory & Compliance",
			"fieldtype": "Section Break",
			"insert_after": "tax_id",
			"collapsible": 1,
		},
		{
			"fieldname": "kamil_license_number",
			"label": "License Number",
			"fieldtype": "Data",
			"insert_after": "kamil_compliance_section",
		},
		{
			"fieldname": "kamil_license_expiry",
			"label": "License Expiry",
			"fieldtype": "Date",
			"insert_after": "kamil_license_number",
		},
		{
			"fieldname": "kamil_license_file",
			"label": "Trading / Business License",
			"fieldtype": "Attach",
			"insert_after": "kamil_license_expiry",
		},
		{
			"fieldname": "kamil_compliance_col",
			"fieldtype": "Column Break",
			"insert_after": "kamil_license_file",
		},
		{
			"fieldname": "kamil_certificate_of_incorporation",
			"label": "Certificate of Incorporation",
			"fieldtype": "Attach",
			"insert_after": "kamil_compliance_col",
		},
		{
			"fieldname": "kamil_cr12",
			"label": "CR12",
			"fieldtype": "Attach",
			"insert_after": "kamil_certificate_of_incorporation",
			"description": "Company shareholding certificate issued by the registrar.",
		},
		{
			"fieldname": "kamil_kra_pin",
			"label": "KRA PIN",
			"fieldtype": "Data",
			"insert_after": "kamil_cr12",
			"description": "Leave blank to fall back to the Tax ID above.",
		},
		{
			"fieldname": "kamil_postal_address",
			"label": "Postal Address",
			"fieldtype": "Small Text",
			"insert_after": "kamil_kra_pin",
			"description": "Free-text postal address. The physical address still lives on the linked Address record.",
		},
		# Frappe creates this itself when a workflow is attached, but the app's Customer
		# list reads it as a column — so guarantee it exists even if the workflow below
		# is skipped, otherwise the list query would fail on an unknown field.
		# Same definition Workflow.create_custom_field_for_workflow_state() uses.
		{
			"fieldname": "workflow_state",
			"label": "Workflow State",
			"fieldtype": "Link",
			"options": "Workflow State",
			"hidden": 1,
			"allow_on_submit": 1,
			"no_copy": 1,
			"insert_after": "kamil_postal_address",
		},
	],
	# Suppliers need the same paperwork on file as customers do.
	"Supplier": [
		{
			"fieldname": "kamil_compliance_section",
			"label": "Statutory & Compliance",
			"fieldtype": "Section Break",
			"insert_after": "tax_id",
			"collapsible": 1,
		},
		{
			"fieldname": "kamil_license_number",
			"label": "License Number",
			"fieldtype": "Data",
			"insert_after": "kamil_compliance_section",
		},
		{
			"fieldname": "kamil_license_expiry",
			"label": "License Expiry",
			"fieldtype": "Date",
			"insert_after": "kamil_license_number",
		},
		{
			"fieldname": "kamil_license_file",
			"label": "Trading / Business License",
			"fieldtype": "Attach",
			"insert_after": "kamil_license_expiry",
		},
		{
			"fieldname": "kamil_compliance_col",
			"fieldtype": "Column Break",
			"insert_after": "kamil_license_file",
		},
		{
			"fieldname": "kamil_certificate_of_incorporation",
			"label": "Certificate of Incorporation",
			"fieldtype": "Attach",
			"insert_after": "kamil_compliance_col",
		},
		{
			"fieldname": "kamil_cr12",
			"label": "CR12",
			"fieldtype": "Attach",
			"insert_after": "kamil_certificate_of_incorporation",
			"description": "Company shareholding certificate issued by the registrar.",
		},
	],
	"Payment Request": [
		{
			"fieldname": "kamil_expense_section",
			"label": "Expense",
			"fieldtype": "Section Break",
			"insert_after": "cost_center",
			"collapsible": 1,
		},
		{
			"fieldname": "kamil_is_expense",
			"label": "Is an Expense",
			"fieldtype": "Check",
			"insert_after": "kamil_expense_section",
			"description": "Ticked when this request was raised as a direct expense rather than against an existing invoice.",
			"read_only": 1,
		},
		{
			"fieldname": "kamil_expense_account",
			"label": "Expense Account",
			"fieldtype": "Link",
			"options": "Account",
			"insert_after": "kamil_is_expense",
			"depends_on": "kamil_is_expense",
			"read_only": 1,
		},
		{
			"fieldname": "kamil_approval_col",
			"fieldtype": "Column Break",
			"insert_after": "kamil_expense_account",
		},
		{
			"fieldname": "kamil_approved_by",
			"label": "Approved By",
			"fieldtype": "Link",
			"options": "User",
			"insert_after": "kamil_approval_col",
			"read_only": 1,
		},
		{
			"fieldname": "kamil_approved_on",
			"label": "Approved On",
			"fieldtype": "Datetime",
			"insert_after": "kamil_approved_by",
			"read_only": 1,
		},
		{
			"fieldname": "kamil_rejection_reason",
			"label": "Rejection Reason",
			"fieldtype": "Small Text",
			"insert_after": "kamil_approved_on",
			"read_only": 1,
		},
	],
}


def create_custom_fields() -> None:
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields as _create

	# Only touch doctypes that actually exist, so the app still installs on a site
	# without the full ERPNext accounts module.
	fields = {dt: defs for dt, defs in CUSTOM_FIELDS.items() if frappe.db.exists("DocType", dt)}
	if fields:
		_create(fields, ignore_validate=True, update=True)


# ---------------------------------------------------------------------------
# Customer approval workflow
# ---------------------------------------------------------------------------

CUSTOMER_WORKFLOW = "Kamil Customer Approval"

# Customer is not submittable, so every state stays at docstatus 0 and the workflow
# only drives `workflow_state` plus who may edit.
CUSTOMER_STATES = [
	{"state": "Draft", "doc_status": "0", "allow_edit": "Sales User", "style": "Warning"},
	{"state": "Pending Approval", "doc_status": "0", "allow_edit": "Sales Manager", "style": "Warning"},
	{"state": "Approved", "doc_status": "0", "allow_edit": "Accounts Manager", "style": "Success"},
	{"state": "Rejected", "doc_status": "0", "allow_edit": "Sales Manager", "style": "Danger"},
]

CUSTOMER_TRANSITIONS = [
	{"state": "Draft", "action": "Submit for Approval", "next_state": "Pending Approval", "allowed": "Sales User"},
	{"state": "Pending Approval", "action": "Approve", "next_state": "Approved", "allowed": "Accounts Manager"},
	{"state": "Pending Approval", "action": "Reject", "next_state": "Rejected", "allowed": "Accounts Manager"},
	{"state": "Rejected", "action": "Resubmit", "next_state": "Pending Approval", "allowed": "Sales User"},
]


def _ensure_workflow_masters() -> None:
	"""Workflow States and Actions are master records; create any that are missing."""
	for state in CUSTOMER_STATES:
		if not frappe.db.exists("Workflow State", state["state"]):
			frappe.get_doc(
				{"doctype": "Workflow State", "workflow_state_name": state["state"], "style": state.get("style") or ""}
			).insert(ignore_permissions=True)

	for transition in CUSTOMER_TRANSITIONS:
		if not frappe.db.exists("Workflow Action Master", transition["action"]):
			frappe.get_doc(
				{"doctype": "Workflow Action Master", "workflow_action_name": transition["action"]}
			).insert(ignore_permissions=True)


def create_customer_workflow() -> None:
	"""Install the Customer approval workflow, leaving an existing one alone.

	We do not overwrite a workflow that is already there — sites often tune states and
	roles by hand, and clobbering that on every migrate would be hostile.
	"""
	if not frappe.db.exists("DocType", "Customer"):
		return

	# Any active workflow on Customer wins; only install ours if there is none.
	existing = frappe.db.get_value("Workflow", {"document_type": "Customer", "is_active": 1}, "name")
	if existing:
		return

	# If our workflow is already on the site, leave its is_active flag exactly as the
	# site set it. Re-enabling it here would undo a deliberate deactivation — and an
	# active workflow locks Customer editing to the roles named in `allow_edit`, which
	# is enough to stop an admin without those roles from creating a Customer at all.
	if frappe.db.exists("Workflow", CUSTOMER_WORKFLOW):
		return

	_ensure_workflow_masters()

	missing_roles = [
		role
		for role in {s.get("allow_edit") for s in CUSTOMER_STATES} | {t["allowed"] for t in CUSTOMER_TRANSITIONS}
		if role and not frappe.db.exists("Role", role)
	]
	if missing_roles:
		frappe.log_error(
			f"Skipped {CUSTOMER_WORKFLOW}: missing roles {', '.join(sorted(missing_roles))}",
			"Kamil Setup",
		)
		return

	workflow = frappe.get_doc(
		{
			"doctype": "Workflow",
			"workflow_name": CUSTOMER_WORKFLOW,
			"document_type": "Customer",
			"workflow_state_field": "workflow_state",
			"is_active": 1,
			"send_email_alert": 0,
			# Customer has its own `disabled` flag; don't let the workflow drive `status`.
			"override_status": 0,
			"states": [
				{"state": s["state"], "doc_status": s["doc_status"], "allow_edit": s["allow_edit"]}
				for s in CUSTOMER_STATES
			],
			"transitions": [
				{
					"state": t["state"],
					"action": t["action"],
					"next_state": t["next_state"],
					"allowed": t["allowed"],
					"allow_self_approval": 0,
				}
				for t in CUSTOMER_TRANSITIONS
			],
		}
	)
	workflow.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Desk workspace
# ---------------------------------------------------------------------------

WORKSPACE = "Kamil"
WORKSPACE_ICON = "retail"
WORKSPACE_COLOR = "orange"


def create_workspace() -> None:
	"""A Kamil entry with an icon in the desk sidebar, opening the app at /kamil.

	The app itself is a standalone frontend, so this is a URL workspace rather than a
	page of cards. An existing workspace is left alone apart from its icon and link —
	sites reorder and rename these by hand, and clobbering that on every migrate
	would be hostile.
	"""
	if not frappe.db.exists("DocType", "Workspace"):
		return

	if frappe.db.exists("Workspace", WORKSPACE):
		doc = frappe.get_doc("Workspace", WORKSPACE)
		changed = False
		if not doc.icon:
			doc.icon = WORKSPACE_ICON
			changed = True
		if doc.type == "URL" and not doc.external_link:
			doc.external_link = "/kamil"
			changed = True
		if changed:
			doc.save(ignore_permissions=True)
		return

	doc = frappe.get_doc(
		{
			"doctype": "Workspace",
			"label": WORKSPACE,
			"title": WORKSPACE,
			"type": "URL",
			"external_link": "/kamil",
			"icon": WORKSPACE_ICON,
			"indicator_color": WORKSPACE_COLOR,
			"public": 1,
			"content": "[]",
			"app": "kamil",
		}
	)
	# `module` is a link, so only set it once Frappe has created the Module Def.
	if frappe.db.exists("Module Def", WORKSPACE):
		doc.module = WORKSPACE

	try:
		doc.insert(ignore_permissions=True)
	except Exception:
		# A workspace is a convenience, never a reason for an install to fail.
		frappe.log_error(frappe.get_traceback(), "Kamil Setup: workspace")


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def after_install() -> None:
	setup_kamil()


def after_migrate() -> None:
	setup_kamil()


def setup_kamil() -> None:
	"""Idempotent: safe to run on every migrate."""
	create_custom_fields()
	create_customer_workflow()
	create_workspace()
	frappe.db.commit()
