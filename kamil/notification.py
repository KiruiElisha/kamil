"""WhatsApp as a channel on Frappe's Notification doctype.

Frappe dispatches a notification with a hard-coded if/elif over Email, Slack, SMS and
System Notification — there is no hook for a new channel. So the controller is extended
(see ``extend_doctype_class`` in hooks.py) and the option is added to the Channel field
with a property setter (see kamil/setup.py). Everything else about a notification —
conditions, schedules, recipients, the message template — keeps working as it does for
any other channel.

Recipients: WhatsApp needs a phone number, so a recipient row's *Receiver By Document
Field* should name a field holding one (`phone_number`, `mobile_no`, `contact_mobile`,
…). When it names something else, or names a role, the app falls back to resolving the
document's party phone the same way the rest of the app does.
"""

import frappe
from frappe.utils import strip_html_tags

WHATSAPP_CHANNEL = "WhatsApp"

# Fields that plausibly hold a phone number, tried in order when a recipient row does
# not name one itself.
_PHONE_FIELDS = ("phone_number", "mobile_no", "contact_mobile", "contact_phone", "phone", "whatsapp_no")


class KamilNotificationMixin:
	"""Adds the WhatsApp channel to Notification."""

	def send_notification_by_channel(self, doc, context):
		if self.channel != WHATSAPP_CHANNEL:
			return super().send_notification_by_channel(doc, context)

		try:
			self.send_a_whatsapp_msg(doc, context)
			# Honour the same "also raise a system notification" flag the other channels do.
			if self.send_system_notification:
				self.create_system_notification(doc, context)
		except Exception:
			self.log_error("Failed to send WhatsApp Notification")

	# -- WhatsApp ----------------------------------------------------------------

	def send_a_whatsapp_msg(self, doc, context):
		from kamil.whatsapp import send_text

		numbers = self.get_whatsapp_numbers(doc)
		if not numbers:
			frappe.log_error(
				f"{self.name}: no phone number found on {doc.doctype} {doc.name}",
				"Kamil WhatsApp Notification",
			)
			return

		message = frappe.render_template(self.message or "", context)
		message = strip_html_tags(message).strip()
		if self.subject:
			subject = frappe.render_template(self.subject, context) if "{" in self.subject else self.subject
			message = f"{subject}\n\n{message}" if message else subject

		for number in numbers:
			send_text(number, message)

	def get_whatsapp_numbers(self, doc) -> list:
		"""Phone numbers this notification should reach, deduplicated."""
		numbers = []

		for recipient in self.recipients or []:
			if recipient.condition and not self.evaluate_recipient_condition(recipient, doc):
				continue

			field = recipient.receiver_by_document_field
			if field:
				# The field may be given as "fieldname" or "fieldname,parentfield" —
				# Frappe's email path splits on the comma, so do the same here.
				value = doc.get(field.split(",")[0])
				if value:
					numbers.append(value)

			if recipient.receiver_by_role:
				numbers.extend(self.get_role_phone_numbers(recipient.receiver_by_role))

		if not numbers:
			numbers = self.guess_document_phone(doc)

		seen = set()
		return [n for n in numbers if n and not (n in seen or seen.add(n))]

	def evaluate_recipient_condition(self, recipient, doc) -> bool:
		try:
			return bool(frappe.safe_eval(recipient.condition, None, {"doc": doc.as_dict()}))
		except Exception:
			# A condition that cannot be evaluated should not silently include everybody.
			self.log_error("Failed to evaluate recipient condition")
			return False

	def get_role_phone_numbers(self, role: str) -> list:
		users = frappe.get_all(
			"Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent", distinct=True
		)
		if not users:
			return []
		rows = frappe.get_all(
			"User", filters={"name": ("in", users), "enabled": 1}, fields=["mobile_no", "phone"]
		)
		return [r.mobile_no or r.phone for r in rows if r.mobile_no or r.phone]

	def guess_document_phone(self, doc) -> list:
		"""Last resort: a phone field on the document, or its party's number."""
		for field in _PHONE_FIELDS:
			if doc.meta.has_field(field) and doc.get(field):
				return [doc.get(field)]

		try:
			from kamil.api import resolve_document_phone

			number = resolve_document_phone(doc.doctype, doc.name)
			return [number] if number else []
		except Exception:
			return []
