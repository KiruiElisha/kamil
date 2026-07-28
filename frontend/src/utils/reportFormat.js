// Formatting shared by every tabular report in the app — the query reports under
// /report/:key and the Report tab of each list view — so a currency, a date or a
// negative number looks the same wherever it is shown.

const NUMERIC = ['Currency', 'Float', 'Int', 'Percent']

/** Numbers are right-aligned and get tabular figures so columns line up. */
export function isNumeric(column) {
  return NUMERIC.includes(column?.fieldtype)
}

/** Link columns the app knows how to drill into (see ReportTable). */
export const PARTY_DOCTYPES = ['Customer', 'Supplier']

/**
 * Which doctype a cell points at, when the app knows how to drill into it.
 *
 * AR/AP Summary declare the party column as a Dynamic Link whose `options` names
 * another column (`party_type`) holding the actual doctype, so the row is needed
 * to resolve it.
 */
export function linkTarget(column, row) {
  const options = (column?.options || '').trim()
  if (column?.fieldtype === 'Dynamic Link') {
    const doctype = row?.[options]
    return PARTY_DOCTYPES.includes(doctype) ? doctype : ''
  }
  if (column?.fieldtype !== 'Link') return ''
  if (PARTY_DOCTYPES.includes(options)) return options
  if (options === 'Account') return 'Account'
  return ''
}

export function formatValue(value, column, currency) {
  if (value === null || value === undefined || value === '') return ''
  const fieldtype = column?.fieldtype || 'Data'
  if (fieldtype === 'Currency') {
    try {
      return new Intl.NumberFormat('en-KE', {
        style: 'currency',
        currency: currency || 'KES',
        maximumFractionDigits: 0,
      }).format(value)
    } catch {
      return value
    }
  }
  if (fieldtype === 'Float' || fieldtype === 'Percent') {
    return Number(value).toLocaleString('en-KE', { maximumFractionDigits: 2 })
  }
  if (fieldtype === 'Int') return Number(value).toLocaleString('en-KE')
  if (fieldtype === 'Date' || fieldtype === 'Datetime') {
    return new Date(value).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
  }
  if (fieldtype === 'Check') return value ? 'Yes' : 'No'
  // Query reports hand back anchor tags for links; the app renders its own.
  return typeof value === 'string' ? value.replace(/<[^>]*>/g, '') : value
}

/** A row that sums up the ones above it — ERPNext flags these in several ways. */
export function isTotalRow(row) {
  if (!row) return false
  if (row.is_total || row.is_total_row || row.bold) return true
  const label = String(row.account_name || row.account || row.party || row.label || row.name || '')
  return /^(total|grand total|closing|opening|net )/i.test(label.trim())
}

/** Group headers in tree-shaped statements (Balance Sheet, Trial Balance, …). */
export function isGroupRow(row) {
  return !!(row && (row.is_group || (row.indent !== undefined && Number(row.indent) === 0)))
}

export function csvFor(columns, rows) {
  const esc = (v) => {
    const str = v === null || v === undefined ? '' : String(v)
    return /[",\n]/.test(str) ? `"${str.replace(/"/g, '""')}"` : str
  }
  const head = columns.map((c) => esc(c.label)).join(',')
  const body = rows.map((r) => columns.map((c) => esc(r[c.fieldname])).join(',')).join('\n')
  // BOM keeps Excel happy with UTF-8
  return '﻿' + head + '\n' + body
}

export function downloadBlob(content, filename, type = 'text/csv;charset=utf-8;') {
  const url = URL.createObjectURL(new Blob([content], { type }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
