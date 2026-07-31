"""Plate numbers, written the same way everywhere.

A plate is typed differently by everyone — "KDW 578Q", "kdw578q", " KDW578Q " — and the
app matches on it constantly: the vehicle is named after its plate, warehouses are named
after the plate and trailer, and every transport document carries copies of both. One
stray space and the same lorry looks like two.

There is a desk client script doing this on the Vehicle form. This does the same thing
server-side, so it also applies to the app, to imports, to the API, and to the plate
fields copied onto invoices and orders — none of which run desk scripts.
"""

import re

PLATE_FIELDS = ("license_plate", "custom_license_plate", "custom_trailer_plate")

_WHITESPACE = re.compile(r"\s+")


def normalize_plate(value: str | None) -> str | None:
	"""Upper-case, with every space removed. Matches the desk script exactly."""
	if not value or not isinstance(value, str):
		return value
	return _WHITESPACE.sub("", value).upper()


def normalize_plates(doc, method=None) -> None:
	"""Tidy every plate field the document has. Guarded on the field existing, so this
	is a no-op on a site without the transport customisation."""
	for field in PLATE_FIELDS:
		if not doc.meta.has_field(field):
			continue
		value = doc.get(field)
		cleaned = normalize_plate(value)
		if cleaned and cleaned != value:
			doc.set(field, cleaned)
