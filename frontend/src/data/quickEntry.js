// Quick-entry metadata (the fields needed to create a record from a link field),
// fetched once per doctype and shared by every dropdown on the page.
import { call } from 'frappe-ui'

const cache = new Map()

export function getQuickEntry(doctype) {
  if (!doctype) return Promise.resolve({ can_create: false, fields: [] })
  if (!cache.has(doctype)) {
    cache.set(
      doctype,
      call('kamil.api.get_quick_entry', { doctype }).catch(() => ({
        doctype,
        can_create: false,
        fields: [],
      })),
    )
  }
  return cache.get(doctype)
}

/** Drop a cached entry, e.g. after roles change. */
export function clearQuickEntry(doctype) {
  if (doctype) cache.delete(doctype)
  else cache.clear()
}
