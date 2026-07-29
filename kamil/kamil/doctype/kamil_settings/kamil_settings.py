# Copyright (c) 2026, Rono and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class KamilSettings(Document):
	def validate(self):
		# The approver's own address is the sensible default, so the two fields cannot
		# drift apart without someone deliberately overriding the email.
		if self.payment_approver and not self.payment_approver_email:
			self.payment_approver_email = frappe.db.get_value("User", self.payment_approver, "email")
