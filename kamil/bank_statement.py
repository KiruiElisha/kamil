"""Bank statements: read a file, show what is in it, create Bank Transactions.

Kenyan bank exports are all the same shape wearing different hats — a date, a
narrative, and the money either leaving or arriving, sometimes as two columns and
sometimes as one signed column. So the parser works by *recognising* columns rather
than by hard-coding a layout per bank: the header row is found wherever it sits (KCB
and Absa both print account details above it), and each column is matched to a role by
its heading.

That means a statement whose headings we have not seen still parses as long as it says
something like "date", "description" and "debit"/"credit". `KNOWN_HEADERS` below is
where a bank's own wording gets added when it does not.

Nothing is written by parsing. The rows come back for review and only `import_rows`
creates Bank Transactions — skipping any that are already on file, so re-uploading an
overlapping statement cannot double-count.
"""

import csv
import io
import re

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

# Column headings, lower-cased, mapped to the role they play. Longest match wins, so
# "value date" beats "date" when a statement carries both.
KNOWN_HEADERS = {
	"date": (
		"transaction date", "value date", "posting date", "txn date", "date posted", "date",
	),
	"description": (
		"transaction details", "narrative", "description", "particulars", "details",
		"transaction remarks", "remarks",
	),
	"reference": (
		"reference number", "transaction reference", "cheque number", "reference no", "reference",
		"cheque no", "transaction id", "receipt no",
	),
	"withdrawal": ("withdrawal", "debit amount", "debit", "money out", "paid out", "dr amount"),
	"deposit": ("deposit", "credit amount", "credit", "money in", "paid in", "cr amount"),
	# Some exports carry one signed column instead of two.
	"amount": ("amount", "transaction amount", "value"),
	"balance": ("running balance", "closing balance", "balance"),
}

_NUMBER = re.compile(r"-?[\d,]+(?:\.\d+)?")


def _role_for(header: str) -> str | None:
	"""Which role a column heading plays, if any."""
	text = re.sub(r"\s+", " ", (header or "").strip().lower())
	if not text:
		return None

	best_role, best_len = None, 0
	for role, candidates in KNOWN_HEADERS.items():
		for candidate in candidates:
			if candidate in text and len(candidate) > best_len:
				best_role, best_len = role, len(candidate)
	return best_role


def _to_amount(value) -> float:
	"""Bank amounts arrive as '1,234.50', '(1,234.50)' for negatives, or blank."""
	if value is None or value == "":
		return 0.0
	if isinstance(value, (int, float)):
		return flt(value)

	text = str(value).strip()
	negative = text.startswith("(") and text.endswith(")")
	match = _NUMBER.search(text.replace(" ", ""))
	if not match:
		return 0.0
	amount = flt(match.group(0).replace(",", ""))
	return -amount if negative else amount


# 01/07/2026 is the 1st of July here, not the 7th of January. frappe's getdate reads
# it the American way round and *succeeds*, so day-first has to be tried first rather
# than kept as a fallback — otherwise a July statement quietly imports into January.
_DAY_FIRST = re.compile(r"^\s*(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})\s*$")
_TEXT_DATE_FORMATS = ("%d-%b-%Y", "%d %b %Y", "%d-%B-%Y", "%d %B %Y", "%b %d, %Y")


def _to_date(value):
	"""A statement date, read day-first as every Kenyan bank prints it."""
	if not value:
		return None

	import datetime

	if isinstance(value, (datetime.datetime, datetime.date)):
		return value.date() if isinstance(value, datetime.datetime) else value

	text = str(value).strip()

	match = _DAY_FIRST.match(text)
	if match:
		day, month, year = (int(g) for g in match.groups())
		if year < 100:
			year += 2000
		try:
			return datetime.date(year, month, day)
		except ValueError:
			# Not a real day-first date (13/25/2026): fall through and let getdate try.
			pass

	for pattern in _TEXT_DATE_FORMATS:
		try:
			return datetime.datetime.strptime(text.split()[0] if pattern.startswith("%d-") else text, pattern).date()
		except ValueError:
			continue

	try:
		return getdate(text)
	except Exception:
		return None


def _is_pdf(content: bytes, filename: str) -> bool:
	return filename.lower().endswith(".pdf") or content[:5] == b"%PDF-"


def _rows_from_file(content: bytes, filename: str) -> list[list]:
	"""Every row of the file, as lists of cells — CSV or XLSX."""
	if filename.lower().endswith((".xlsx", ".xls")):
		from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file

		return read_xlsx_file_from_attached_file(fcontent=content) or []

	text = content.decode("utf-8-sig", errors="replace")
	# Sniff the delimiter: some exports are semicolon-separated.
	try:
		dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
	except Exception:
		dialect = csv.excel
	return [row for row in csv.reader(io.StringIO(text), dialect)]


def _find_header(rows: list[list]) -> tuple[int, dict]:
	"""Locate the header row and map its columns to roles.

	Statements print account details above the table, so the header is not row 0. The
	header is the first row where at least a date column and one money column appear.
	"""
	for index, row in enumerate(rows[:40]):
		mapping = {}
		for position, cell in enumerate(row):
			role = _role_for(str(cell) if cell is not None else "")
			if role and role not in mapping:
				mapping[role] = position
		has_money = {"withdrawal", "deposit", "amount"} & set(mapping)
		if "date" in mapping and has_money:
			return index, mapping
	return -1, {}


@frappe.whitelist()
def parse_statement(file_url: str) -> dict:
	"""Read an uploaded statement and return its rows for review. Writes nothing.

	PDFs from KCB and Absa are read by kamil/bank_statement_pdf.py, which checks each
	parse against the statement's own totals. CSV and XLSX exports go through the
	column-recognising reader below.
	"""
	if not file_url:
		frappe.throw(_("Upload a statement first."))

	file_doc = frappe.get_doc("File", {"file_url": file_url})
	file_doc.check_permission("read")
	content = file_doc.get_content()
	if isinstance(content, str):
		content = content.encode("utf-8")

	filename = file_doc.file_name or file_url

	if _is_pdf(content, filename):
		from kamil.bank_statement_pdf import parse_pdf

		parsed = parse_pdf(content)
		sections = parsed.get("sections") or []
		if not sections:
			return {
				"rows": [],
				"sections": [],
				"file_name": filename,
				"error": parsed.get("error")
				or _("No transactions were found in this PDF. If it is a scan rather than a "
					"generated statement, there is no text to read."),
			}

		return {
			"bank": parsed.get("bank"),
			"file_name": filename,
			"sections": [
				{
					"label": _("{0} · account {1} · {2}").format(
						s.get("bank"), s.get("account_no") or "?", s.get("currency") or "?"
					),
					"account_no": s.get("account_no"),
					"currency": s.get("currency"),
					"rows": s["rows"],
					"total_deposits": s.get("total_in"),
					"total_withdrawals": s.get("total_out"),
					"balanced": s.get("balanced", True),
					"checks": s.get("checks") or [],
					"warnings": s.get("warnings") or [],
				}
				for s in sections
			],
			# The first section is what the page shows until another is picked.
			"rows": sections[0]["rows"],
			"total_deposits": sections[0].get("total_in"),
			"total_withdrawals": sections[0].get("total_out"),
		}

	rows = _rows_from_file(content, filename)
	header_index, mapping = _find_header(rows)
	if header_index < 0:
		return {
			"rows": [],
			"columns": [],
			"error": _(
				"Could not find a header row with a date and an amount. The statement's column "
				"names may need adding to the parser."
			),
			"sample": [[str(c) for c in row[:8]] for row in rows[:5]],
		}

	parsed = []
	for row in rows[header_index + 1 :]:
		if not any(str(cell or "").strip() for cell in row):
			continue

		def cell(role):
			position = mapping.get(role)
			return row[position] if position is not None and position < len(row) else None

		date = _to_date(cell("date"))
		if not date:
			continue  # totals and footers trail the table; they have no date

		deposit = _to_amount(cell("deposit"))
		withdrawal = _to_amount(cell("withdrawal"))
		if not deposit and not withdrawal:
			# One signed column: positive is money in, negative is money out.
			amount = _to_amount(cell("amount"))
			deposit, withdrawal = (amount, 0.0) if amount > 0 else (0.0, abs(amount))
		if not deposit and not withdrawal:
			continue  # opening-balance markers carry no movement

		parsed.append(
			{
				"date": str(date),
				"description": str(cell("description") or "").strip(),
				"reference_number": str(cell("reference") or "").strip(),
				"deposit": flt(abs(deposit)),
				"withdrawal": flt(abs(withdrawal)),
				"balance": _to_amount(cell("balance")),
			}
		)

	return {
		"rows": parsed,
		"columns": sorted(mapping),
		"header_row": header_index + 1,
		"file_name": filename,
		"total_deposits": flt(sum(r["deposit"] for r in parsed)),
		"total_withdrawals": flt(sum(r["withdrawal"] for r in parsed)),
	}


def _already_imported(bank_account: str, row: dict) -> str | None:
	"""The transaction on file for this row, if there is one.

	Matched on the bank account, the date and the amounts, plus the reference when the
	statement carries one — enough to make re-uploading an overlapping statement safe.
	"""
	filters = {
		"bank_account": bank_account,
		"date": row.get("date"),
		"deposit": flt(row.get("deposit")),
		"withdrawal": flt(row.get("withdrawal")),
		"docstatus": ("<", 2),
	}
	if row.get("reference_number"):
		filters["reference_number"] = row["reference_number"]
	return frappe.db.get_value("Bank Transaction", filters, "name")


@frappe.whitelist()
def import_rows(bank_account: str, rows: str | list, submit: int | str = 1) -> dict:
	"""Create Bank Transactions from reviewed rows, skipping ones already on file."""
	if not frappe.has_permission("Bank Transaction", "create"):
		frappe.throw(_("You are not allowed to create bank transactions."), frappe.PermissionError)
	if not bank_account or not frappe.db.exists("Bank Account", bank_account):
		frappe.throw(_("Pick the bank account this statement belongs to."))

	rows = frappe.parse_json(rows) if isinstance(rows, str) else (rows or [])
	if not isinstance(rows, list) or not rows:
		frappe.throw(_("Nothing to import."))

	company = frappe.db.get_value("Bank Account", bank_account, "company")
	created, skipped, failed = [], [], []

	for row in rows:
		if not row.get("date") or (not flt(row.get("deposit")) and not flt(row.get("withdrawal"))):
			continue
		existing = _already_imported(bank_account, row)
		if existing:
			skipped.append(existing)
			continue

		try:
			doc = frappe.get_doc(
				{
					"doctype": "Bank Transaction",
					"date": row["date"],
					"bank_account": bank_account,
					"company": company,
					"deposit": flt(row.get("deposit")),
					"withdrawal": flt(row.get("withdrawal")),
					"description": (row.get("description") or "")[:500],
					"reference_number": (row.get("reference_number") or "")[:140] or None,
				}
			)
			doc.insert(ignore_permissions=True)
			if cint(submit):
				doc.submit()
			created.append(doc.name)
		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "Kamil bank statement import")
			failed.append({"date": row.get("date"), "error": str(e)[:200]})

	return {
		"created": created,
		"skipped": skipped,
		"failed": failed,
		"summary": _("{0} created, {1} already on file, {2} failed.").format(
			len(created), len(skipped), len(failed)
		),
	}


@frappe.whitelist()
def list_bank_accounts() -> list:
	"""Bank accounts a statement can be imported against."""
	if not frappe.has_permission("Bank Account", "read"):
		return []

	rows = frappe.get_list(
		"Bank Account",
		filters={"is_company_account": 1},
		fields=["name", "account", "bank", "company"],
		order_by="name asc",
		limit_page_length=50,
	)
	return [
		{"label": f"{r.name}{' · ' + r.bank if r.bank else ''}", "value": r.name, "account": r.account}
		for r in rows
	]


@frappe.whitelist()
def get_reconciliation_summary(bank_account: str, from_date: str | None = None, to_date: str | None = None) -> dict:
	"""How much of what was imported is still unreconciled."""
	if not frappe.has_permission("Bank Transaction", "read"):
		return {}

	filters = {"bank_account": bank_account, "docstatus": 1}
	if from_date and to_date:
		filters["date"] = ("between", [from_date, to_date])

	rows = frappe.get_all(
		"Bank Transaction",
		filters=filters,
		fields=["name", "status", "deposit", "withdrawal", "unallocated_amount"],
		limit_page_length=0,
	)
	unreconciled = [r for r in rows if (r.status or "") != "Reconciled"]
	return {
		"transactions": len(rows),
		"unreconciled": len(unreconciled),
		"unallocated": flt(sum(flt(r.unallocated_amount) for r in unreconciled)),
		"deposits": flt(sum(flt(r.deposit) for r in rows)),
		"withdrawals": flt(sum(flt(r.withdrawal) for r in rows)),
	}
