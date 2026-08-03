// One shared permission lookup for the whole app. The sidebar, the bottom nav and the
// reports index all read from this single cached request instead of asking separately.
import { ref, computed } from 'vue'
import { call } from 'frappe-ui'
import { LISTS } from '@/data/doctypes.js'
import { REPORTS } from '@/data/reports.js'

const docPerms = ref({})
const reportPerms = ref({})
const loaded = ref(false)
let inflight = null

function load() {
  if (inflight) return inflight

  // Bank Transaction is not a list in the sidebar, but the Bank Statements page is
  // gated on it, so it has to be part of the same permission fetch.
  const doctypes = [...new Set([...LISTS.map((l) => l.doctype), 'Bank Transaction'])]
  const reports = [...new Set(REPORTS.map((r) => r.report))]

  inflight = Promise.all([
    call('kamil.api.get_nav_permissions', { doctypes: JSON.stringify(doctypes) }),
    call('kamil.api.get_permitted_reports', { reports: JSON.stringify(reports) }),
  ])
    .then(([p, rp]) => {
      docPerms.value = p || {}
      reportPerms.value = rp || {}
    })
    .catch(() => {
      // If the permission check itself fails, assume access and let the server reject
      // individual reads — an empty, unusable sidebar is the worse failure.
      docPerms.value = Object.fromEntries(doctypes.map((d) => [d, { read: true, create: true }]))
      reportPerms.value = Object.fromEntries(reports.map((r) => [r, true]))
    })
    .finally(() => {
      loaded.value = true
    })

  return inflight
}

/** Force a re-read, e.g. after roles change. */
export function refreshPermissions() {
  inflight = null
  loaded.value = false
  return load()
}

export function usePermissions() {
  load()

  // Reads stay optimistic while loading so navigation never looks empty; the server
  // still enforces. Creates are gated strictly — never offer a button bound to fail.
  const canRead = (doctype) => !loaded.value || docPerms.value[doctype]?.read !== false
  const canCreate = (doctype) => loaded.value && docPerms.value[doctype]?.create === true
  const canRunReport = (report) => reportPerms.value[report] !== false

  return {
    loaded,
    canRead,
    canCreate,
    canRunReport,
    visibleLists: computed(() => LISTS.filter((l) => canRead(l.doctype))),
    visibleReports: computed(() => REPORTS.filter((r) => canRunReport(r.report))),
  }
}
