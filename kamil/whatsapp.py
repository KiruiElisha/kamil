"""WhatsApp sending for the app, on top of the site's ``whatsapp_integration`` app.

Two things make sending from the app unreliable if we simply call the integration:

1. The gateway (waclient.com) goes to sleep when it is idle. The first request after
   an idle spell is slow, and sometimes fails outright, so we *ping it first* — a
   cheap request that wakes it up before the real payload is sent, plus a retry with
   backoff if the send itself still trips over a sleeping gateway.
2. The integration posts with **no timeout and no retry**, so a sleeping gateway made
   the app hang until the browser gave up. Every request here has explicit connect and
   read timeouts.

Credentials, the Whatsapp Feedback log and the phone-number rules all stay with the
integration app — this module only owns the transport.
"""

import time

import frappe
from frappe import _
from frappe.utils import cint, get_url, now_datetime

API_URL = "https://waclient.com/api/send"

# (connect, read). The gateway is slow after idling, hence the generous read timeout —
# but never unbounded, which is what made a sleeping gateway hang the app.
SEND_TIMEOUT = (10, 90)
WAKE_TIMEOUT = (5, 20)

SEND_ATTEMPTS = 3
WAKE_ATTEMPTS = 2
RETRY_BACKOFF = (2, 5)  # seconds before the 2nd and 3rd send attempt

# How long a successful ping is trusted for, so a burst of messages pings once.
AWAKE_TTL = 120
_AWAKE_KEY = "kamil:whatsapp-gateway-awake"


# ---------------------------------------------------------------------------
# Waking the gateway
# ---------------------------------------------------------------------------


@frappe.whitelist()
def warm_gateway(force: int | str = 0) -> dict:
	"""Ping the gateway so it is awake by the time a message is sent.

	The app calls this as soon as the user opens the WhatsApp panel — by the time they
	have picked a print format and pressed Send, the gateway has already woken up.
	Safe to call often: a successful ping is remembered for a couple of minutes.
	"""
	import requests

	if not cint(force) and frappe.cache().get_value(_AWAKE_KEY):
		return {"awake": True, "cached": True, "took_ms": 0}

	started = time.monotonic()
	error = None
	for attempt in range(WAKE_ATTEMPTS):
		try:
			# Any HTTP answer means the host is up — the endpoint rejects a bare GET,
			# which is exactly what we want: it wakes without sending anything.
			requests.get(API_URL, timeout=WAKE_TIMEOUT, headers={"Accept": "application/json"})
			frappe.cache().set_value(_AWAKE_KEY, "1", expires_in_sec=AWAKE_TTL)
			return {"awake": True, "cached": False, "took_ms": int((time.monotonic() - started) * 1000)}
		except Exception as e:
			error = str(e)
			if attempt + 1 < WAKE_ATTEMPTS:
				time.sleep(1)

	return {
		"awake": False,
		"cached": False,
		"took_ms": int((time.monotonic() - started) * 1000),
		"error": error,
	}


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------


def _settings(sender: str | None = None) -> dict:
	"""Gateway credentials, from the integration app's own settings."""
	try:
		from whatsapp_integration.service.rest import get_whatsapp_settings

		return get_whatsapp_settings(sender)
	except ImportError:
		frappe.throw(_("The WhatsApp Integration app is not installed on this site."))


def _post(payload: dict) -> dict:
	"""POST to the gateway: wake it, then send with timeouts and a couple of retries.

	Only transport failures are retried (timeouts, dropped connections, 5xx) — those
	mean nothing was delivered. A response the gateway actually produced is returned
	as-is, so a message is never sent twice.
	"""
	import requests

	warm_gateway()

	last_error = None
	for attempt in range(SEND_ATTEMPTS):
		try:
			response = requests.post(
				API_URL,
				json=payload,
				timeout=SEND_TIMEOUT,
				headers={
					"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
					"Accept": "application/json",
					"Content-Type": "application/json",
				},
			)
			if response.status_code >= 500:
				last_error = f"HTTP {response.status_code}"
				raise requests.exceptions.RequestException(last_error)

			try:
				return response.json()
			except ValueError:
				return {"status": "error", "message": (response.text or "")[:500] or "Empty response"}
		except requests.exceptions.RequestException as e:
			last_error = str(e) or e.__class__.__name__
			if attempt + 1 < SEND_ATTEMPTS:
				time.sleep(RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)])
				# A sleeping gateway is the usual cause — wake it again before retrying.
				frappe.cache().delete_value(_AWAKE_KEY)
				warm_gateway(force=1)

	frappe.log_error(f"WhatsApp gateway unreachable after {SEND_ATTEMPTS} attempts: {last_error}", "Kamil WhatsApp")
	return {"status": "error", "message": _("WhatsApp gateway did not respond: {0}").format(last_error)}


_OK_STATUSES = ("success", "sent", "queued", "processing", "ok", "true", "1")


def _result(response: dict, phone: str) -> dict:
	"""Normalise the gateway's several response shapes into one the app can read."""
	response = response if isinstance(response, dict) else {"status": "error", "message": str(response)}

	status = str(response.get("status") or "").lower()
	# Text sends answer with `data`, media sends with `message`; both nest key.id.
	body = response.get("data") if isinstance(response.get("data"), dict) else response.get("message")
	message_id = body.get("key", {}).get("id") if isinstance(body, dict) else None

	success = status in _OK_STATUSES or (not status and bool(message_id))
	error = None
	if not success:
		error = response.get("error") or (body if isinstance(body, str) else None) or _("Unknown error")

	return {
		"success": success,
		"status": status or ("sent" if success else "error"),
		"message_id": message_id,
		"phone_number": phone,
		"error": None if success else str(error),
	}


def _record_feedback(phone: str, result: dict) -> None:
	"""Log the send the same way the integration app does, so both agree."""
	try:
		frappe.get_doc(
			{
				"doctype": "Whatsapp Feedback",
				"phone_number": phone,
				"status": result.get("status"),
				"key_id": result.get("message_id"),
				"date": frappe.utils.nowdate(),
			}
		).insert(ignore_permissions=True)
	except Exception:
		# Logging must never be the reason a delivered message looks failed.
		frappe.log_error(frappe.get_traceback(), "Kamil WhatsApp Feedback")


# ---------------------------------------------------------------------------
# Phone numbers and media URLs
# ---------------------------------------------------------------------------


def normalize_number(phone: str) -> str:
	"""Gateway-ready number: digits only, with a country code."""
	try:
		from whatsapp_integration.api.whatsapp.whatsapp import normalize_phone_number

		phone = normalize_phone_number(phone) or ""
	except ImportError:
		phone = "".join(ch for ch in str(phone or "") if ch.isdigit() or ch == "+").lstrip("+")

	phone = "".join(ch for ch in str(phone) if ch.isdigit())
	# Local Kenyan numbers, in either 07xx or 7xx shape.
	if phone.startswith("0"):
		phone = "254" + phone[1:]
	elif len(phone) <= 9 and phone:
		phone = "254" + phone[-9:]
	return phone


def _validate_number(phone: str) -> None:
	if not phone:
		frappe.throw(_("Please provide a phone number."))
	if not (10 <= len(phone) <= 15):
		frappe.throw(_("{0} does not look like a valid WhatsApp number.").format(phone))


def _public_base_url() -> str:
	"""Base URL the gateway will fetch attachments from.

	The gateway downloads the PDF itself, so this has to be reachable from the public
	internet. Sites whose internal URL is not public can set ``kamil_whatsapp_public_url``
	in site_config.json.
	"""
	base = frappe.conf.get("kamil_whatsapp_public_url") or frappe.conf.get("host_name") or get_url() or ""
	base = base.strip().rstrip("/")
	if base and not base.startswith("http"):
		base = f"https://{base}"
	return base


_LOCAL_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0", "::1")


def _media_warning(url: str) -> str | None:
	"""Flag a media URL the gateway will not be able to download."""
	from urllib.parse import urlparse

	parsed = urlparse(url)
	host = (parsed.hostname or "").lower()
	if not host:
		return _("The site has no public URL configured, so the attachment cannot be fetched.")
	if host in _LOCAL_HOSTS or host.endswith(".local") or host.endswith(".localhost"):
		is_local = True
	else:
		is_local = host.startswith("192.168.") or host.startswith("10.") or host.startswith("172.16.")
	if is_local or (parsed.port and parsed.port not in (80, 443)):
		return _(
			"The attachment link ({0}) is not reachable from the internet, so WhatsApp may show the "
			"message without the document. Set kamil_whatsapp_public_url in site_config.json to the "
			"site's public address."
		).format(url)
	return None


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------


def send_text(to_number: str, message: str, sender: str | None = None) -> dict:
	"""Plain text message through the woken gateway."""
	phone = normalize_number(to_number)
	_validate_number(phone)

	settings = _settings(sender)
	result = _result(
		_post(
			{
				"number": phone,
				"type": "text",
				"message": message,
				"instance_id": settings["instance_id"],
				"access_token": settings["access_token"],
			}
		),
		phone,
	)
	_record_feedback(phone, result)
	return result


def send_media(
	to_number: str,
	message: str,
	media_url: str,
	file_name: str | None = None,
	sender: str | None = None,
) -> dict:
	"""Message with a document attached, fetched by the gateway from `media_url`."""
	phone = normalize_number(to_number)
	_validate_number(phone)

	settings = _settings(sender)
	result = _result(
		_post(
			{
				"number": phone,
				"type": "media",
				"message": message,
				"media_url": media_url,
				"filename": file_name,
				"instance_id": settings["instance_id"],
				"access_token": settings["access_token"],
			}
		),
		phone,
	)
	_record_feedback(phone, result)
	return result


def _document_pdf(doctype: str, name: str, print_format: str | None) -> bytes:
	"""Render a document to PDF, tolerating images the print format cannot load."""
	from frappe.utils.pdf import get_pdf

	html = frappe.get_print(doctype, name, print_format=print_format or None, no_letterhead=0)
	try:
		from whatsapp_integration.api.whatsapp.whatsapp import make_html_pdf_ready

		html = make_html_pdf_ready(html)
	except ImportError:
		pass

	return get_pdf(
		html,
		options={
			"load-error-handling": "ignore",
			"load-media-error-handling": "ignore",
			"no-stop-slow-scripts": True,
			"quiet": "",
		},
	)


def send_document(
	doctype: str,
	name: str,
	phone_number: str | None = None,
	message: str | None = None,
	sender: str | None = None,
	print_format: str | None = None,
) -> dict:
	"""Send a document's PDF to a party over WhatsApp.

	Returns a normalised ``{success, status, error, …}`` result rather than raising, so
	the dialog can show what happened without losing what the user typed.
	"""
	frappe.has_permission(doctype, "read", doc=name, throw=True)

	if not phone_number:
		from kamil.api import resolve_document_phone

		phone_number = resolve_document_phone(doctype, name)

	phone = normalize_number(phone_number)
	_validate_number(phone)

	try:
		pdf_content = _document_pdf(doctype, name, print_format)
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Kamil WhatsApp PDF Generation Failed")
		return {
			"success": False,
			"status": "pdf_error",
			"error": _("Could not generate the PDF for {0} {1}: {2}").format(doctype, name, str(e)),
		}

	file_name = f"{doctype}_{name}_{now_datetime().strftime('%Y%m%d_%H%M%S')}.pdf"
	file_name = file_name.replace(" ", "_").replace("/", "-")

	# The gateway downloads the attachment itself, so the file has to be public — a
	# private file would come back as a login page. The URL is unguessable and the
	# file stays attached to the document, which is how the integration app does it too.
	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": file_name,
			"content": pdf_content,
			"is_private": 0,
			"attached_to_doctype": doctype,
			"attached_to_name": name,
		}
	).insert(ignore_permissions=True)

	if not file_doc.file_url:
		return {
			"success": False,
			"status": "file_error",
			"error": _("Could not store the PDF for sending."),
		}

	media_url = f"{_public_base_url()}{file_doc.file_url}"
	warning = _media_warning(media_url)

	if not message:
		message = _("Please find attached {0}: {1}").format(_(doctype), name)

	result = send_media(phone, message, media_url, file_name.replace(".pdf", ""), sender)
	result["media_url"] = media_url
	if warning:
		result["warning"] = warning
	if not result["success"]:
		frappe.log_error(f"{doctype} {name} -> {phone}: {result.get('error')}", "Kamil WhatsApp Send Failed")
	return result
