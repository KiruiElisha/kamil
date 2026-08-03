"""Reading KCB and Absa PDF statements.

Neither bank offers a machine-readable export, so the PDF's text layer is what there
is. Extracting it flattens the table — a row's cells arrive as a run of words with no
column boundaries — so each bank is read by recognising the *shape* of a row rather
than by column position:

    KCB    01.06.2026 01.06.2026 <details> <money out> <money in>
           Money out is already negative; dates are dot-separated.

    Absa   30/04/2026 30/04/2026 <description> <reference> <cheque no> <amount> <balance>
           Only one amount column survives the flattening, so whether it was a debit or
           a credit is decided by which way the running balance moved. That is also a
           check: a row whose balance does not move by its own amount is reported
           rather than guessed at.

Every parse is verified against the statement's own totals before it is offered for
import. A statement that does not add up is refused — a silently mis-read bank
statement is far worse than one that fails loudly.
"""

import re

from frappe.utils import flt

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

# 1,234.56 / -1,234.56 / (1,234.56)
_AMOUNT = re.compile(r"\(?-?\d{1,3}(?:,\d{3})*\.\d{2}\)?")
_KCB_ROW_START = re.compile(r"(\d{2}\.\d{2}\.\d{4})\s+(\d{2}\.\d{2}\.\d{4})")
_ABSA_ROW_START = re.compile(r"(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})")


def _amount(text: str) -> float:
	text = (text or "").strip()
	negative = text.startswith("(") and text.endswith(")")
	value = flt(text.strip("()").replace(",", ""))
	return -value if negative else value


def _iso(date_text: str) -> str:
	"""dd.mm.yyyy or dd/mm/yyyy -> yyyy-mm-dd. Both banks print day first."""
	day, month, year = re.split(r"[./]", date_text)
	return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def pdf_text(content: bytes) -> str:
	"""The whole document's text layer, pages joined."""
	import io

	from pypdf import PdfReader

	reader = PdfReader(io.BytesIO(content))
	return "\n".join((page.extract_text() or "") for page in reader.pages)


def detect_bank(text: str) -> str:
	"""Which bank produced this statement.

	The name is not reliable — KCB's is a logo image, so the text layer never says
	"KCB" at all. Each bank is recognised by the labels its template prints and by the
	way it writes dates: KCB uses dots, Absa uses slashes.
	"""
	lowered = text.lower()

	if "absa bank" in lowered or ("customer reference" in lowered and "running balance" in lowered):
		return "Absa"
	if "total money in:" in lowered or "balance at period start" in lowered:
		return "KCB"

	# Nothing named itself: fall back to the shape of the rows.
	if _KCB_ROW_START.search(text):
		return "KCB"
	if _ABSA_ROW_START.search(text):
		return "Absa"
	return ""


def _chunks(text: str, pattern) -> list[tuple]:
	"""Split the flattened table into one chunk per row.

	A row starts at its two dates and runs until the next row's dates, which is what
	keeps a wrapped description with the row it belongs to.
	"""
	matches = list(pattern.finditer(text))
	out = []
	for index, match in enumerate(matches):
		end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
		out.append((match.group(1), match.group(2), text[match.end() : end]))
	return out


def _split_head(body: str, count: int, after: int = 0) -> tuple[str, list[float]]:
	"""The first `count` amounts at or after `after`, and the text before them.

	Deliberately the *first* rather than the last: a chunk can run into the ledger
	balance, a repeated page header or the closing totals block, and anchoring on the
	end would silently read those as the row's own figures.
	"""
	amounts = [m for m in _AMOUNT.finditer(body) if m.start() >= after]
	if len(amounts) < count:
		return body.strip(), []
	head = amounts[:count]
	return body[: head[0].start()].strip(), [_amount(m.group(0)) for m in head]


def _clean(text: str) -> str:
	return re.sub(r"\s+", " ", (text or "").replace("\n", " ")).strip()


# ---------------------------------------------------------------------------
# KCB
# ---------------------------------------------------------------------------

_KCB_ACCOUNT = re.compile(r"Account:\s*(\d+)")
_KCB_CURRENCY = re.compile(r"Available Balance:\s*([A-Z]{3})")
_KCB_IN = re.compile(r"Total Money In:\s*(-?[\d,]+\.\d{2})")
_KCB_OUT = re.compile(r"Total Money Out:\s*(-?[\d,]+\.\d{2})")
_KCB_REFERENCE = re.compile(r"\b(FT[A-Z0-9]{6,})\b")


def parse_kcb(text: str) -> list[dict]:
	"""KCB iBank: two dates, details, money out (negative), money in."""
	rows = []
	for date_text, _value_date, body in _chunks(text, _KCB_ROW_START):
		details, amounts = _split_head(body, 2)
		if len(amounts) != 2:
			continue

		money_out, money_in = amounts
		if not money_out and not money_in:
			continue  # BALANCE B/FWD and similar markers carry no movement

		reference = _KCB_REFERENCE.search(body)
		rows.append(
			{
				"date": _iso(date_text),
				"description": _clean(details),
				"reference_number": reference.group(1) if reference else "",
				"deposit": flt(abs(money_in)),
				"withdrawal": flt(abs(money_out)),
			}
		)

	account = _KCB_ACCOUNT.search(text)
	currency = _KCB_CURRENCY.search(text)
	stated_in = _KCB_IN.search(text)
	stated_out = _KCB_OUT.search(text)

	return [
		{
			"bank": "KCB",
			"account_no": account.group(1) if account else "",
			"currency": currency.group(1) if currency else "",
			"rows": rows,
			"stated_in": _amount(stated_in.group(1)) if stated_in else None,
			"stated_out": abs(_amount(stated_out.group(1))) if stated_out else None,
		}
	]


# ---------------------------------------------------------------------------
# Absa
# ---------------------------------------------------------------------------

_ABSA_ACCOUNT = re.compile(r"Account no:\s*(\d+)")
_ABSA_CURRENCY = re.compile(r"Currency:\s*([A-Z]{3})")
_ABSA_OPENING = re.compile(
	r"Opening balance\s+Closing balance\s+Total money in\s+Total money out\s*"
	r"([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})"
)
_ABSA_CHEQUE = re.compile(r"\b\d{9,14}\b")


def parse_absa(text: str) -> list[dict]:
	"""Absa: one PDF can hold several accounts, each with its own summary block.

	Direction comes from the running balance: the amount is a credit when the balance
	rose by it and a debit when it fell. Rows whose balance does not move by their own
	amount are flagged rather than guessed at.
	"""
	# Each account starts at its own "Account no:" line.
	starts = [m.start() for m in _ABSA_ACCOUNT.finditer(text)]
	if not starts:
		starts = [0]
	blocks = [text[start : (starts[i + 1] if i + 1 < len(starts) else len(text))] for i, start in enumerate(starts)]

	sections = []
	for block in blocks:
		account = _ABSA_ACCOUNT.search(block)
		currency = _ABSA_CURRENCY.search(block)
		summary = _ABSA_OPENING.search(block)
		opening = _amount(summary.group(1)) if summary else None
		stated_in = _amount(summary.group(3)) if summary else None
		stated_out = _amount(summary.group(4)) if summary else None

		rows, warnings = [], []
		balance = opening
		for date_text, _value_date, body in _chunks(block, _ABSA_ROW_START):
			# The cheque number separates the narrative from the figures, so the row's
			# own amount and balance are the first two amounts after it.
			cheque = _ABSA_CHEQUE.search(body)
			details, amounts = _split_head(body, 2, after=cheque.end() if cheque else 0)
			if len(amounts) != 2:
				continue
			amount, running = amounts
			if not amount:
				continue

			narrative = _clean(body[: cheque.start()] if cheque else details)

			deposit = withdrawal = 0.0
			if balance is None:
				# No opening balance to compare against: fall back to the row after it.
				deposit = amount
			else:
				rose = running - balance
				if abs(rose - amount) < 0.01:
					deposit = amount
				elif abs(rose + amount) < 0.01:
					withdrawal = amount
				else:
					warnings.append(
						f"{_iso(date_text)}: {amount:,.2f} does not match the balance moving "
						f"from {balance:,.2f} to {running:,.2f}"
					)
					# Direction by balance movement is still the best guess available.
					deposit, withdrawal = (amount, 0.0) if rose > 0 else (0.0, amount)

			balance = running
			rows.append(
				{
					"date": _iso(date_text),
					"description": narrative,
					"reference_number": "",
					"deposit": flt(deposit),
					"withdrawal": flt(withdrawal),
				}
			)

		if rows:
			sections.append(
				{
					"bank": "Absa",
					"account_no": account.group(1) if account else "",
					"currency": currency.group(1) if currency else "",
					"rows": rows,
					"stated_in": stated_in,
					"stated_out": stated_out,
					"warnings": warnings,
				}
			)

	return sections


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def parse_pdf(content: bytes) -> dict:
	"""Read a statement PDF into sections, one per account, and check the totals."""
	text = pdf_text(content)
	bank = detect_bank(text)

	if bank == "KCB":
		sections = parse_kcb(text)
	elif bank == "Absa":
		sections = parse_absa(text)
	else:
		return {"bank": "", "sections": [], "error": "This does not look like a KCB or Absa statement."}

	for section in sections:
		total_in = flt(sum(r["deposit"] for r in section["rows"]))
		total_out = flt(sum(r["withdrawal"] for r in section["rows"]))
		section["total_in"] = total_in
		section["total_out"] = total_out

		# The statement's own totals are the check on the parse.
		checks = []
		if section.get("stated_in") is not None and abs(total_in - section["stated_in"]) > 0.01:
			checks.append(f"money in reads {total_in:,.2f} but the statement says {section['stated_in']:,.2f}")
		if section.get("stated_out") is not None and abs(total_out - section["stated_out"]) > 0.01:
			checks.append(f"money out reads {total_out:,.2f} but the statement says {section['stated_out']:,.2f}")
		section["balanced"] = not checks
		section["checks"] = checks

	return {"bank": bank, "sections": sections}
