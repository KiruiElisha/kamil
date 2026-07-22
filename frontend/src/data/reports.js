// Standard ERPNext query reports surfaced inside the app (run via kamil.api.run_report).
import ArrowDownLeft from '~icons/lucide/arrow-down-left'
import ArrowUpRight from '~icons/lucide/arrow-up-right'
import BookOpen from '~icons/lucide/book-open'
import Package from '~icons/lucide/package'
import Wallet from '~icons/lucide/wallet'

const asOn = [{ fieldname: 'report_date', label: 'As on', default: 'today' }]
const range = [
  { fieldname: 'from_date', label: 'From', default: 'month_start' },
  { fieldname: 'to_date', label: 'To', default: 'today' },
]

export const REPORTS = [
  { key: 'accounts-receivable', title: 'Accounts Receivable', report: 'Accounts Receivable', icon: ArrowDownLeft, filters: asOn },
  { key: 'accounts-payable', title: 'Accounts Payable', report: 'Accounts Payable', icon: ArrowUpRight, filters: asOn },
  { key: 'ar-summary', title: 'AR Summary', report: 'Accounts Receivable Summary', icon: Wallet, filters: asOn },
  { key: 'ap-summary', title: 'AP Summary', report: 'Accounts Payable Summary', icon: Wallet, filters: asOn },
  { key: 'general-ledger', title: 'General Ledger', report: 'General Ledger', icon: BookOpen, filters: range },
  { key: 'stock-balance', title: 'Stock Balance', report: 'Stock Balance', icon: Package, filters: range },
]

export function findReport(key) {
  return REPORTS.find((r) => r.key === key)
}
