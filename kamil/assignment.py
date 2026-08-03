"""Telling somebody they have been given something to do.

Frappe raises a ToDo whenever a document is assigned — from the desk, from this app,
or from any script — so hooking ToDo is what makes the WhatsApp go out however the
assignment was made, rather than only from the app's own button.

The number comes from the Employee record (`cell_number`), because that is where the
company keeps staff numbers; the User's own mobile is a fallback for people who have a
login but no employee record.
"""

import frappe
from frappe import _
from frappe.utils import get_url

# Where to look for the assignee's number, in order.
EMPLOYEE_PHONE_FIELDS = ("cell_number", "personal_email")
USER_PHONE_FIELDS = ("mobile_no", "phone")


def employee_phone(user: str) -> str | None:
	"""The assignee's mobile number: their Employee record first, then their User."""
	if not user or user in ("Administrator", "Guest"):
		return None

	if frappe.db.exists("DocType", "Employee"):
		employee = frappe.db.get_value(
			"Employee", {"user_id": user, "status": "Active"}, ["name", "cell_number"], as_dict=True
		) or frappe.db.get_value("Employee", {"user_id": user}, ["name", "cell_number"], as_dict=True)
		if employee and employee.get("cell_number"):
			return employee["cell_number"]

	row = frappe.db.get_value("User", user, USER_PHONE_FIELDS, as_dict=True) or {}
	for field in USER_PHONE_FIELDS:
		if row.get(field):
			return row[field]
	return None


def _message(todo) -> str:
	"""What the assignee reads on their phone."""
	what = (todo.description or "").strip()
	# Frappe's own descriptions arrive as HTML fragments.
	what = frappe.utils.strip_html_tags(what).strip() or _("a document")

	lines = [_("You have been assigned: {0}").format(what[:300])]
	if todo.reference_type and todo.reference_name:
		lines.append(f"{_(todo.reference_type)}: {todo.reference_name}")
		lines.append(
			get_url(f"/app/{frappe.scrub(todo.reference_type).replace('_', '-')}/{todo.reference_name}")
		)
	if todo.date:
		lines.append(_("Due {0}").format(frappe.utils.formatdate(todo.date)))
	if todo.priority and todo.priority != "Medium":
		lines.append(_("Priority: {0}").format(todo.priority))
	return "\n".join(lines)


def send_assignment_whatsapp(name: str) -> dict:
	"""Send the assignment message. Split out so it can run in the background."""
	todo = frappe.get_doc("ToDo", name)
	phone = employee_phone(todo.allocated_to)
	if not phone:
		return {"sent": False, "error": "no phone number on file"}

	from kamil.whatsapp import send_text

	result = send_text(phone, _message(todo))
	if not result.get("success"):
		frappe.log_error(
			f"Assignment WhatsApp to {todo.allocated_to} ({phone}) failed: {result.get('error')}",
			"Kamil assignment notification",
		)
	return result


def notify_assignment(doc, method=None) -> None:
	"""On a new ToDo, WhatsApp the person it was given to.

	Queued so a sleeping gateway cannot hold up the save that created it; if the queue
	is unavailable the message is sent inline rather than dropped.
	"""
	if doc.status and doc.status != "Open":
		return
	if not doc.allocated_to:
		return
	# Assigning something to yourself does not need a message about it.
	if doc.allocated_to == frappe.session.user:
		return
	if "whatsapp_integration" not in (frappe.get_installed_apps() or []):
		return

	from kamil.background import enqueue_or_run

	enqueue_or_run("kamil.assignment.send_assignment_whatsapp", name=doc.name)
