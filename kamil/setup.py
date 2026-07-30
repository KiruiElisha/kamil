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
# Two steps and no more: a customer is submitted for approval, then approved. There is
# no separate verification stage afterwards — approving *is* the verification, and the
# KYC status is set from the paperwork itself (see kamil/customer.py).
CUSTOMER_STATES = [
	{"state": "Draft", "doc_status": "0", "allow_edit": "Sales User", "style": "Warning"},
	{"state": "Pending Approval", "doc_status": "0", "allow_edit": "Sales Manager", "style": "Warning"},
	{"state": "Approved", "doc_status": "0", "allow_edit": "Accounts Manager", "style": "Success"},
	{"state": "Rejected", "doc_status": "0", "allow_edit": "Sales User", "style": "Danger"},
]

CUSTOMER_TRANSITIONS = [
	# Step 1 — the salesperson sends it up
	{"state": "Draft", "action": "Submit for Approval", "next_state": "Pending Approval", "allowed": "Sales User"},
	# Step 2 — and it is approved (or sent back)
	{"state": "Pending Approval", "action": "Approve", "next_state": "Approved", "allowed": "Accounts Manager"},
	{"state": "Pending Approval", "action": "Reject", "next_state": "Rejected", "allowed": "Accounts Manager"},
	{"state": "Rejected", "action": "Resubmit", "next_state": "Pending Approval", "allowed": "Sales User"},
]


def _ensure_workflow_masters(states, transitions) -> None:
	"""Workflow States and Actions are master records; create any that are missing."""
	for state in states:
		if not frappe.db.exists("Workflow State", state["state"]):
			frappe.get_doc(
				{"doctype": "Workflow State", "workflow_state_name": state["state"], "style": state.get("style") or ""}
			).insert(ignore_permissions=True)

	for transition in transitions:
		if not frappe.db.exists("Workflow Action Master", transition["action"]):
			frappe.get_doc(
				{"doctype": "Workflow Action Master", "workflow_action_name": transition["action"]}
			).insert(ignore_permissions=True)


def _install_workflow(name, doctype, states, transitions, state_field="workflow_state", override_status=0) -> None:
	"""Install a workflow, leaving an existing one on the doctype alone.

	Sites tune states and roles by hand; clobbering that on every migrate would be
	hostile. A workflow is only installed when the doctype has none active.
	"""
	if not frappe.db.exists("DocType", doctype):
		return

	if frappe.db.get_value("Workflow", {"document_type": doctype, "is_active": 1}, "name"):
		return

	_ensure_workflow_masters(states, transitions)

	if frappe.db.exists("Workflow", name):
		frappe.db.set_value("Workflow", name, "is_active", 1)
		return

	missing_roles = [
		role
		for role in {s.get("allow_edit") for s in states} | {t["allowed"] for t in transitions}
		if role and not frappe.db.exists("Role", role)
	]
	if missing_roles:
		frappe.log_error(f"Skipped {name}: missing roles {', '.join(sorted(missing_roles))}", "Kamil Setup")
		return

	frappe.get_doc(
		{
			"doctype": "Workflow",
			"workflow_name": name,
			"document_type": doctype,
			"workflow_state_field": state_field,
			"is_active": 1,
			"send_email_alert": 0,
			"override_status": override_status,
			"states": [
				{"state": s["state"], "doc_status": s["doc_status"], "allow_edit": s["allow_edit"]} for s in states
			],
			"transitions": [
				{
					"state": t["state"],
					"action": t["action"],
					"next_state": t["next_state"],
					"allowed": t["allowed"],
					"allow_self_approval": t.get("allow_self_approval", 0),
				}
				for t in transitions
			],
		}
	).insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Purchase approval — two steps before an order is placed
# ---------------------------------------------------------------------------
#
# Purchase Order is submittable, so the workflow drives docstatus as well as state:
# an order is only submitted (docstatus 1) once the second approver signs it off, and
# nothing can be ordered on one person's say-so.

PURCHASE_WORKFLOW = "Kamil Purchase Approval"

PURCHASE_STATES = [
	{"state": "Draft", "doc_status": "0", "allow_edit": "Purchase User", "style": "Warning"},
	{"state": "Pending Review", "doc_status": "0", "allow_edit": "Purchase Manager", "style": "Warning"},
	{"state": "Pending Approval", "doc_status": "0", "allow_edit": "Accounts Manager", "style": "Warning"},
	{"state": "Approved", "doc_status": "1", "allow_edit": "Accounts Manager", "style": "Success"},
	{"state": "Rejected", "doc_status": "0", "allow_edit": "Purchase User", "style": "Danger"},
]

PURCHASE_TRANSITIONS = [
	# Step 1 — the buyer sends it up, purchasing checks it
	{"state": "Draft", "action": "Submit for Review", "next_state": "Pending Review", "allowed": "Purchase User"},
	{"state": "Pending Review", "action": "Review", "next_state": "Pending Approval", "allowed": "Purchase Manager"},
	{"state": "Pending Review", "action": "Reject", "next_state": "Rejected", "allowed": "Purchase Manager"},
	# Step 2 — finance approves, which submits the order
	{"state": "Pending Approval", "action": "Approve", "next_state": "Approved", "allowed": "Accounts Manager"},
	{"state": "Pending Approval", "action": "Reject", "next_state": "Rejected", "allowed": "Accounts Manager"},
	# Back to the buyer to fix and resend
	{"state": "Rejected", "action": "Resubmit", "next_state": "Pending Review", "allowed": "Purchase User"},
]


def create_purchase_workflow() -> None:
	"""Two-step approval on Purchase Orders: purchasing reviews, finance approves."""
	_install_workflow(PURCHASE_WORKFLOW, "Purchase Order", PURCHASE_STATES, PURCHASE_TRANSITIONS)


def create_customer_workflow() -> None:
	"""Install the Customer approval workflow, leaving an existing one alone."""
	# Customer has its own `disabled` flag; don't let the workflow drive `status`.
	_install_workflow(CUSTOMER_WORKFLOW, "Customer", CUSTOMER_STATES, CUSTOMER_TRANSITIONS)


# ---------------------------------------------------------------------------
# Vehicle: trim ERPNext's fleet fields down to what a fuel haulier uses
# ---------------------------------------------------------------------------
#
# Kamil's vehicles are tankers on hire, not a staff fleet: insurance is the
# transporter's business, and nobody records door or wheel counts. Hiding the fields
# is deliberate rather than deleting them — the data (if any was ever entered) stays,
# and a site that wants them back only has to clear the property setter.

VEHICLE_HIDDEN_FIELDS = (
	# Fleet admin ERPNext assumes but Kamil does not keep on the vehicle record
	"insurance_details",  # section holding the four insurance fields below
	"insurance_company",
	"policy_no",
	"start_date",
	"end_date",
	"carbon_check_date",
	"wheels",
	"doors",
	# Not tracked per vehicle here — fuel and mileage live on the transport documents
	"fuel_type",
	"uom",
	"last_odometer",
	"acquisition_date",
	"vehicle_value",
	"chassis_no",
	"location",
)

# Anything this app has hidden in the past but no longer wants hidden. Property
# setters persist, so a field dropped from the list above has to be un-hidden
# explicitly or it would stay invisible forever.
VEHICLE_RESTORED_FIELDS = ("employee",)


def hide_vehicle_fields() -> None:
	"""Hide the Vehicle fields the app has no use for, and restore any it used to
	hide. Idempotent, so it can run on every migrate."""
	if not frappe.db.exists("DocType", "Vehicle"):
		return

	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	meta = frappe.get_meta("Vehicle")
	for fieldname in VEHICLE_HIDDEN_FIELDS:
		df = meta.get_field(fieldname)
		if not df:
			continue
		make_property_setter("Vehicle", fieldname, "hidden", 1, "Check", validate_fields_for_doctype=False)
		# A hidden field that is still mandatory would block every save.
		if df.reqd:
			make_property_setter(
				"Vehicle", fieldname, "reqd", 0, "Check", validate_fields_for_doctype=False
			)

	for fieldname in VEHICLE_RESTORED_FIELDS:
		frappe.db.delete(
			"Property Setter",
			{"doc_type": "Vehicle", "field_name": fieldname, "property": ("in", ("hidden", "reqd"))},
		)

	frappe.clear_cache(doctype="Vehicle")


# ---------------------------------------------------------------------------
# WhatsApp notification channel
# ---------------------------------------------------------------------------


def add_whatsapp_notification_channel() -> None:
	"""Offer WhatsApp alongside Email/SMS on the Notification doctype.

	The sending half lives in kamil/notification.py; this only makes the option
	selectable. Written as a property setter so Frappe's own field definition is left
	alone, and re-derived from the current options each time in case Frappe adds a
	channel of its own.
	"""
	if not frappe.db.exists("DocType", "Notification"):
		return

	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	options = (frappe.get_meta("Notification").get_field("channel") or {}).get("options") or ""
	channels = [c.strip() for c in options.split("\n") if c.strip()]
	if "WhatsApp" in channels:
		return

	channels.append("WhatsApp")
	make_property_setter(
		"Notification", "channel", "options", "\n".join(channels), "Text", validate_fields_for_doctype=False
	)


# ---------------------------------------------------------------------------
# Payment approval role
# ---------------------------------------------------------------------------

PAYMENT_APPROVER_ROLE = "Payment Approver"


def create_payment_approver_role() -> None:
	"""A role whose only job is approving payment requests.

	Approving used to fall to anyone with Accounts User or Accounts Manager, which is
	far wider than the people actually allowed to release money. The role is created
	empty; the one person configured in Kamil Settings gets it automatically so the
	flow keeps working, and anyone else is granted it deliberately.
	"""
	if not frappe.db.exists("Role", PAYMENT_APPROVER_ROLE):
		frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": PAYMENT_APPROVER_ROLE,
				"desk_access": 1,
				"is_custom": 1,
			}
		).insert(ignore_permissions=True)

	# Whoever payment requests are sent to should be able to act on them.
	approver = None
	if frappe.db.exists("DocType", "Kamil Settings"):
		approver = frappe.db.get_single_value("Kamil Settings", "payment_approver")
	if not approver or not frappe.db.exists("User", approver):
		return

	has_role = frappe.db.exists("Has Role", {"parent": approver, "role": PAYMENT_APPROVER_ROLE})
	if not has_role:
		user = frappe.get_doc("User", approver)
		user.append("roles", {"role": PAYMENT_APPROVER_ROLE})
		user.save(ignore_permissions=True)


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
	create_purchase_workflow()
	create_payment_approver_role()
	add_whatsapp_notification_channel()
	hide_vehicle_fields()
	create_workspace()
	frappe.db.commit()
