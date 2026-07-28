"""Master-data screens for the app: Chart of Accounts, users, and per-user email.

Nothing here bypasses permissions — every read goes through ``frappe.get_list`` or an
explicit ``has_permission`` check, and every write goes through a normal document save so
validations and permissions apply exactly as they would on the desk.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt

# ---------------------------------------------------------------------------
# Chart of Accounts
# ---------------------------------------------------------------------------

_ACCOUNT_FIELDS = (
	"name",
	"account_name",
	"account_number",
	"parent_account",
	"is_group",
	"root_type",
	"account_type",
	"account_currency",
	"company",
	"disabled",
	"freeze_account",
	"tax_rate",
	"lft",
	"rgt",
)


@frappe.whitelist()
def get_chart_of_accounts(company: str | None = None, include_disabled: int | str = 0) -> dict:
	"""The whole chart for one company as a nested tree, plus a flat list.

	Returned in one call so the app can offer tree and list views of the same data
	without re-fetching. Charts are small enough (hundreds of rows) for this.
	"""
	if not frappe.has_permission("Account", "read"):
		frappe.throw(_("You are not allowed to view accounts."), frappe.PermissionError)

	from kamil.api import _resolve_company

	company = _resolve_company(company)
	filters = {"company": company}
	if not cint(include_disabled):
		filters["disabled"] = 0

	rows = frappe.get_list(
		"Account",
		filters=filters,
		fields=list(_ACCOUNT_FIELDS),
		order_by="lft asc",
		limit_page_length=0,
	)

	nodes = {}
	for row in rows:
		nodes[row.name] = {
			"name": row.name,
			"account_name": row.account_name,
			"account_number": row.account_number,
			"label": f"{row.account_number} - {row.account_name}" if row.account_number else row.account_name,
			"parent_account": row.parent_account,
			"is_group": cint(row.is_group),
			"root_type": row.root_type,
			"account_type": row.account_type,
			"account_currency": row.account_currency,
			"company": row.company,
			"disabled": cint(row.disabled),
			"freeze_account": row.freeze_account,
			"tax_rate": flt(row.tax_rate),
			"children": [],
		}

	roots = []
	for node in nodes.values():
		parent = nodes.get(node["parent_account"])
		if parent:
			parent["children"].append(node)
		else:
			# Either a real root, or its parent is filtered out (e.g. disabled).
			roots.append(node)

	return {
		"company": company,
		"tree": roots,
		"flat": list(nodes.values()),
		"can_create": bool(frappe.has_permission("Account", "create")),
		"can_write": bool(frappe.has_permission("Account", "write")),
	}


@frappe.whitelist()
def get_account_balances(company: str | None = None, to_date: str | None = None) -> dict:
	"""Closing balance per account, for showing figures next to the tree."""
	if not frappe.has_permission("GL Entry", "read"):
		return {}

	from kamil.api import _resolve_company

	company = _resolve_company(company)
	to_date = to_date or frappe.utils.nowdate()

	rows = frappe.db.sql(
		"""
		select account, sum(debit) - sum(credit) as balance
		from `tabGL Entry`
		where company = %(company)s and is_cancelled = 0 and posting_date <= %(to_date)s
		group by account
		""",
		{"company": company, "to_date": to_date},
		as_dict=True,
	)
	return {r.account: flt(r.balance) for r in rows}


@frappe.whitelist()
def save_account(values: str | dict) -> dict:
	"""Create or update an Account from the app.

	`values.name` present -> update that account, otherwise create a new one.
	"""
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	if not isinstance(values, dict):
		frappe.throw(_("Invalid account details."))

	editable = (
		"account_name",
		"account_number",
		"parent_account",
		"is_group",
		"root_type",
		"account_type",
		"account_currency",
		"company",
		"disabled",
		"tax_rate",
	)

	name = values.get("name")
	if name:
		doc = frappe.get_doc("Account", name)
		doc.check_permission("write")
		# root_type and company are structural; changing them on an existing account
		# corrupts the tree, so they are ignored on update.
		for field in editable:
			if field in values and field not in ("company", "root_type"):
				doc.set(field, values[field])
		doc.save()
	else:
		if not frappe.has_permission("Account", "create"):
			frappe.throw(_("You are not allowed to create accounts."), frappe.PermissionError)
		if not values.get("account_name"):
			frappe.throw(_("Account Name is required."))
		if not values.get("parent_account"):
			frappe.throw(_("Parent Account is required."))

		from kamil.api import _resolve_company

		doc = frappe.new_doc("Account")
		doc.company = _resolve_company(values.get("company"))
		for field in editable:
			if field in values and field != "company":
				doc.set(field, values[field])
		doc.insert()

	return {
		"name": doc.name,
		"account_name": doc.account_name,
		"parent_account": doc.parent_account,
		"is_group": cint(doc.is_group),
		"root_type": doc.root_type,
	}


@frappe.whitelist()
def get_account_parents(company: str | None = None, txt: str = "") -> list:
	"""Group accounts only — the valid parents when adding an account."""
	if not frappe.has_permission("Account", "read"):
		return []

	from kamil.api import _resolve_company

	filters = {"company": _resolve_company(company), "is_group": 1}
	if txt:
		filters["name"] = ("like", f"%{txt}%")

	rows = frappe.get_list("Account", filters=filters, fields=["name"], order_by="name asc", limit_page_length=50)
	return [{"label": r.name, "value": r.name} for r in rows]


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

_USER_FIELDS = ("name", "full_name", "first_name", "last_name", "email", "enabled", "user_type", "last_active")


@frappe.whitelist()
def list_users(search: str = "", limit: int = 100) -> dict:
	"""Users, for the admin screen. Read permission on User is enforced by get_list."""
	if not frappe.has_permission("User", "read"):
		frappe.throw(_("You are not allowed to view users."), frappe.PermissionError)

	filters = {}
	or_filters = {}
	if search:
		or_filters = {"full_name": ("like", f"%{search}%"), "name": ("like", f"%{search}%")}

	rows = frappe.get_list(
		"User",
		filters=filters,
		or_filters=or_filters,
		fields=list(_USER_FIELDS),
		order_by="enabled desc, full_name asc",
		limit_page_length=cint(limit),
	)

	return {
		"users": [
			{
				"name": r.name,
				"full_name": r.full_name or r.name,
				"email": r.email or r.name,
				"enabled": cint(r.enabled),
				"user_type": r.user_type,
				"last_active": str(r.last_active or "") or None,
			}
			for r in rows
		],
		"can_create": bool(frappe.has_permission("User", "create")),
		"can_write": bool(frappe.has_permission("User", "write")),
	}


@frappe.whitelist()
def get_user(name: str) -> dict:
	"""One user with their roles."""
	doc = frappe.get_doc("User", name)
	doc.check_permission("read")
	return {
		"name": doc.name,
		"full_name": doc.full_name,
		"first_name": doc.first_name,
		"last_name": doc.last_name,
		"email": doc.email,
		"enabled": cint(doc.enabled),
		"user_type": doc.user_type,
		"mobile_no": doc.mobile_no,
		"roles": sorted(r.role for r in doc.roles),
	}


@frappe.whitelist()
def list_assignable_roles() -> list:
	"""Roles that can be handed out — excludes the built-in pseudo roles."""
	if not frappe.has_permission("Role", "read"):
		return []

	rows = frappe.get_list(
		"Role",
		filters={"disabled": 0, "is_custom": 0},
		fields=["name"],
		order_by="name asc",
		limit_page_length=0,
	)
	skip = {"All", "Guest", "Administrator", "Desk User"}
	return [{"label": r.name, "value": r.name} for r in rows if r.name not in skip]


@frappe.whitelist()
def save_user(values: str | dict) -> dict:
	"""Create or update a user, optionally replacing their role set.

	Roles are only touched when a `roles` list is supplied, so saving a name change
	cannot silently wipe someone's access.
	"""
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	if not isinstance(values, dict):
		frappe.throw(_("Invalid user details."))

	email = (values.get("name") or values.get("email") or "").strip().lower()
	if not email:
		frappe.throw(_("Email is required."))

	is_new = not frappe.db.exists("User", email)
	if is_new:
		if not frappe.has_permission("User", "create"):
			frappe.throw(_("You are not allowed to create users."), frappe.PermissionError)
		doc = frappe.new_doc("User")
		doc.email = email
	else:
		doc = frappe.get_doc("User", email)
		doc.check_permission("write")

	for field in ("first_name", "last_name", "mobile_no", "user_type"):
		if values.get(field):
			doc.set(field, values[field])
	if not doc.first_name:
		doc.first_name = email.split("@")[0]
	if "enabled" in values:
		doc.enabled = cint(values["enabled"])

	roles = values.get("roles")
	if isinstance(roles, list):
		allowed = {r["value"] for r in list_assignable_roles()}
		requested = {r for r in roles if r in allowed}
		doc.set("roles", [])
		for role in sorted(requested):
			doc.append("roles", {"role": role})

	if is_new:
		# Frappe emails the welcome/reset link itself; we never handle a password here.
		doc.insert()
	else:
		doc.save()

	return {"name": doc.name, "enabled": cint(doc.enabled), "created": is_new}


@frappe.whitelist()
def set_user_enabled(name: str, enabled: int | str) -> dict:
	"""Enable or disable a user without touching anything else."""
	doc = frappe.get_doc("User", name)
	doc.check_permission("write")

	if name == frappe.session.user and not cint(enabled):
		frappe.throw(_("You cannot disable your own account."))
	if name == "Administrator" and not cint(enabled):
		frappe.throw(_("The Administrator account cannot be disabled."))

	doc.enabled = cint(enabled)
	doc.save()
	return {"name": doc.name, "enabled": cint(doc.enabled)}


# ---------------------------------------------------------------------------
# Per-user email accounts
# ---------------------------------------------------------------------------

# Email Account has no "user" link — Frappe ties an account to a person through
# `email_id`, which is also how frappe.email.smtp picks the outgoing account for a
# sender. So "my" account is the one whose email_id is my own address, and we pin
# email_id to the session user so nobody can set up an account for someone else's
# address and capture their outgoing mail.
_EMAIL_FIELDS = (
	"email_id",
	"login_id",
	"login_id_is_different",
	"smtp_server",
	"smtp_port",
	"use_tls",
	"use_ssl_for_outgoing",
	"enable_outgoing",
	"enable_incoming",
	"email_server",
	"use_imap",
	"use_ssl",
	"incoming_port",
	"awaiting_password",
)

# Kamil's mail is hosted on Zoho, so a mailbox that is being set up for the first time
# starts on Zoho's standard servers and the user only has to supply a password. The
# other presets are here so the same screen still works for a mailbox hosted elsewhere.
EMAIL_PROVIDERS = {
	"Zoho Mail": {
		"smtp_server": "smtp.zoho.com",
		"smtp_port": 587,
		"use_tls": 1,
		"use_ssl_for_outgoing": 0,
		"email_server": "imap.zoho.com",
		"use_imap": 1,
		"use_ssl": 1,
		"incoming_port": 993,
	},
	"Gmail": {
		"smtp_server": "smtp.gmail.com",
		"smtp_port": 587,
		"use_tls": 1,
		"use_ssl_for_outgoing": 0,
		"email_server": "imap.gmail.com",
		"use_imap": 1,
		"use_ssl": 1,
		"incoming_port": 993,
	},
	"Microsoft 365": {
		"smtp_server": "smtp.office365.com",
		"smtp_port": 587,
		"use_tls": 1,
		"use_ssl_for_outgoing": 0,
		"email_server": "outlook.office365.com",
		"use_imap": 1,
		"use_ssl": 1,
		"incoming_port": 993,
	},
}
DEFAULT_EMAIL_PROVIDER = "Zoho Mail"


def _provider_presets() -> list:
	"""Server settings offered by the email screen, the default one first."""
	names = [DEFAULT_EMAIL_PROVIDER] + [p for p in EMAIL_PROVIDERS if p != DEFAULT_EMAIL_PROVIDER]
	return [{"name": name, "values": EMAIL_PROVIDERS[name]} for name in names]


def _my_email_address() -> str:
	"""The signed-in user's own email address."""
	user = frappe.session.user
	return (frappe.db.get_value("User", user, "email") or user or "").strip()


def _my_email_account_name() -> str | None:
	address = _my_email_address()
	if not address:
		return None
	return frappe.db.get_value("Email Account", {"email_id": address}, "name")


@frappe.whitelist()
def get_my_email_account() -> dict:
	"""The current user's own Email Account, if they have set one up."""
	address = _my_email_address()
	name = _my_email_account_name()
	presets = {"providers": _provider_presets(), "default_provider": DEFAULT_EMAIL_PROVIDER}
	if not name:
		return {"exists": False, "email_id": address, **presets}

	doc = frappe.get_doc("Email Account", name)
	if not doc.has_permission("read"):
		return {"exists": False, "email_id": address, **presets}

	data = {"exists": True, "name": doc.name, **presets}
	for field in _EMAIL_FIELDS:
		data[field] = doc.get(field)
	# Never return the password, encrypted or otherwise.
	data.pop("password", None)
	return data


@frappe.whitelist()
def save_my_email_account(values: str | dict) -> dict:
	"""Create or update the signed-in user's own Email Account.

	The password is handed straight to the Email Account document, so Frappe does the
	encrypting and the connection check — this code never stores or logs it. The address
	is always the session user's own, so this cannot be used to touch anyone else's mail.
	"""
	if not frappe.has_permission("Email Account", "create"):
		frappe.throw(_("You are not allowed to set up email accounts."), frappe.PermissionError)

	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	if not isinstance(values, dict):
		frappe.throw(_("Invalid email settings."))

	address = _my_email_address()
	if not address or "@" not in address:
		frappe.throw(_("Your user account has no email address to set up."))

	existing = _my_email_account_name()
	if existing:
		doc = frappe.get_doc("Email Account", existing)
		doc.check_permission("write")
	else:
		doc = frappe.new_doc("Email Account")
		doc.email_account_name = f"{address} (personal)"

	for field in _EMAIL_FIELDS:
		if field in values and field != "email_id":
			doc.set(field, values[field])
	doc.email_id = address  # pinned to the session user, never taken from the payload

	# Server settings left blank fall back to the house provider (Zoho), so supplying
	# a password is enough to get a working mailbox.
	defaults = EMAIL_PROVIDERS[DEFAULT_EMAIL_PROVIDER]
	if cint(doc.enable_outgoing) and not doc.smtp_server:
		for field in ("smtp_server", "smtp_port", "use_tls", "use_ssl_for_outgoing"):
			doc.set(field, defaults[field])
	if cint(doc.enable_incoming) and not doc.email_server:
		for field in ("email_server", "use_imap", "use_ssl", "incoming_port"):
			doc.set(field, defaults[field])

	password = values.get("password")
	if password:
		doc.password = password

	# A personal mailbox must not silently become the site-wide default.
	doc.default_outgoing = 0
	doc.default_incoming = 0

	doc.save()

	return {"name": doc.name, "email_id": doc.email_id, "awaiting_password": cint(doc.awaiting_password)}


@frappe.whitelist()
def delete_my_email_account() -> dict:
	"""Remove the signed-in user's own Email Account."""
	name = _my_email_account_name()
	if not name:
		return {"deleted": False}

	doc = frappe.get_doc("Email Account", name)
	doc.check_permission("delete")
	doc.delete()
	return {"deleted": True, "name": name}
