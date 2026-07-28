// Single source of truth for how field values are coloured across the app, so a
// status looks the same in the desktop table, the mobile card and the viewer.

// frappe-ui Badge themes we rely on: gray, blue, green, orange, red.
const GREEN = 'green'
const BLUE = 'blue'
const ORANGE = 'orange'
const RED = 'red'
const GRAY = 'gray'

// Settled / successful outcomes
const DONE = [
  'Paid', 'Completed', 'Closed', 'Delivered', 'Received', 'Fulfilled', 'Approved',
  'Active', 'Enabled', 'Verified', 'Reconciled', 'Success', 'Confirmed', 'Ordered',
  'Completed and Paid',
]
// In flight — nothing is waiting on us yet
const PROGRESS = [
  'Submitted', 'Open', 'In Progress', 'Working', 'Processing', 'Scheduled',
  'Partially Ordered', 'Partially Received', 'Partly Billed', 'Requested', 'Initiated',
]
// Waiting on somebody — the colour that should catch the eye
const WAITING = [
  'Unpaid', 'Pending', 'Partly Paid', 'Partly Paid and Discounted', 'Unpaid and Discounted',
  'To Bill', 'To Deliver', 'To Deliver and Bill', 'To Receive', 'To Receive and Bill',
  'Issued', 'Transferred', 'Queued', 'Not Started', 'Awaiting Approval', 'Under Review',
  'Draft Approval',
]
// Problems
const BAD = [
  'Overdue', 'Cancelled', 'Failed', 'Rejected', 'Stopped', 'On Hold', 'Expired',
  'Lost', 'Disabled', 'Error', 'Suspended', 'Unreconciled', 'Overdue and Discounted',
]
// Neutral / informational
const NEUTRAL = [
  'Draft', 'Return', 'Credit Note Issued', 'Debit Note Issued', 'Replied', 'Duplicate',
]

const STATUS_THEME = {}
const register = (values, theme) => values.forEach((v) => (STATUS_THEME[v.toLowerCase()] = theme))
register(DONE, GREEN)
register(PROGRESS, BLUE)
register(WAITING, ORANGE)
register(BAD, RED)
register(NEUTRAL, GRAY)

/** Badge theme for a `status`-like value. Unknown values fall back to gray. */
export function statusTheme(status) {
  if (!status) return GRAY
  return STATUS_THEME[String(status).toLowerCase().trim()] || GRAY
}

const DOCSTATUS = {
  0: { label: 'Draft', theme: GRAY },
  1: { label: 'Submitted', theme: BLUE },
  2: { label: 'Cancelled', theme: RED },
}

/** Badge label + theme for a raw numeric docstatus. */
export function docstatusBadge(docstatus) {
  return DOCSTATUS[Number(docstatus)] || DOCSTATUS[0]
}

// Type-ish fields (payment_type, voucher_type, stock_entry_type, …) carry no notion
// of good or bad, but colouring them still makes a long list scannable. Known values
// get a deliberate colour; anything else gets one derived from the text so it stays
// stable between renders instead of shifting around.
const KIND_THEME = {
  receive: GREEN,
  pay: ORANGE,
  'internal transfer': BLUE,
  purchase: ORANGE,
  sales: GREEN,
  'material transfer': BLUE,
  'material issue': ORANGE,
  'material receipt': GREEN,
  manufacture: BLUE,
  repack: BLUE,
  'customer provided': GRAY,
  'journal entry': GRAY,
  'bank entry': BLUE,
  'cash entry': GREEN,
  'contra entry': GRAY,
  'credit note': ORANGE,
  'debit note': ORANGE,
  'opening stock': GRAY,
  'stock reconciliation': BLUE,
}
const PALETTE = [BLUE, GREEN, ORANGE, GRAY]

/** Badge theme for a categorical (non-status) value such as a document type. */
export function kindTheme(value) {
  if (!value) return GRAY
  const key = String(value).toLowerCase().trim()
  if (KIND_THEME[key]) return KIND_THEME[key]
  let hash = 0
  for (let i = 0; i < key.length; i++) hash = (hash * 31 + key.charCodeAt(i)) % 997
  return PALETTE[hash % PALETTE.length]
}

// Tailwind classes for the small indicator dot on KPI cards and notification rows.
const DOT_CLASS = {
  green: 'bg-green-500',
  blue: 'bg-blue-500',
  orange: 'bg-orange-500',
  amber: 'bg-amber-500',
  red: 'bg-red-500',
  gray: 'bg-gray-400',
}

/** Tailwind background class for a coloured indicator dot. */
export function dotClass(color) {
  return DOT_CLASS[color] || DOT_CLASS.gray
}
