"""Running work in the background, without depending on the queue being up.

`frappe.enqueue(..., enqueue_after_commit=True)` does not run at call time — it is
deferred to the commit — so a queue outage surfaces *during the commit* rather than
where the enqueue was written, and takes the transaction with it. A payment request
should not fail to be raised because a PDF could not be queued.

So the queue is checked first and the work runs inline when it is unavailable. Inline
is slower but correct; the alternative is losing the work or losing the document.
"""

import frappe


def queue_available() -> bool:
	"""Whether the background queue can actually be reached right now."""
	try:
		from frappe.utils.background_jobs import get_redis_conn

		conn = get_redis_conn()
		conn.ping()
		return True
	except Exception:
		return False


def enqueue_or_run(method: str, queue: str = "short", **kwargs) -> dict:
	"""Queue `method`, or run it here and now if the queue is down.

	Either way the caller gets a result rather than an exception: this is for work
	that supports the document (a PDF, a notification), never for the document itself.
	"""
	if queue_available():
		try:
			frappe.enqueue(method, queue=queue, enqueue_after_commit=True, **kwargs)
			return {"queued": True}
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Kamil: could not queue {method}")

	try:
		frappe.get_attr(method)(**kwargs)
		return {"queued": False, "ran": True}
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Kamil: {method} failed")
		return {"queued": False, "ran": False}
