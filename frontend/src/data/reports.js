// Standard ERPNext query reports surfaced inside the app (run via kamil.api.run_report).
//
// Each report declares the filters it wants rendered, plus `defaults` for filters the
// report requires but the user never needs to see. `company` is filled in server-side.
//
// Filter `default` tokens understood by ReportView: today, month_start, year_start,
// fiscal_year_start, fiscal_year (the last resolved from the server).
import ArrowDownLeft from '~icons/lucide/arrow-down-left'
import ArrowUpRight from '~icons/lucide/arrow-up-right'
import BookOpen from '~icons/lucide/book-open'
import Package from '~icons/lucide/package'
import Wallet from '~icons/lucide/wallet'
import TrendingUp from '~icons/lucide/trending-up'
import Scale from '~icons/lucide/scale'
import Landmark from '~icons/lucide/landmark'
import Receipt from '~icons/lucide/receipt'
import ShoppingBag from '~icons/lucide/shopping-bag'
import Percent from '~icons/lucide/percent'
import Users from '~icons/lucide/users'
import Truck from '~icons/lucide/truck'
import Target from '~icons/lucide/target'
import Activity from '~icons/lucide/activity'
import Layers from '~icons/lucide/layers'
import Calculator from '~icons/lucide/calculator'

export const REPORT_SECTIONS = [
  'Financial Statements',
  'Receivables & Payables',
  'Ledgers',
  'Sales & Purchases',
  'Stock',
]

// --- filter builders -------------------------------------------------------
const date = (fieldname, label, def) => ({ fieldname, label, fieldtype: 'date', default: def })
const select = (fieldname, label, options, def) => ({
  fieldname,
  label,
  fieldtype: 'select',
  options: options.map((o) => ({ label: o, value: o })),
  default: def,
})
const link = (fieldname, label, doctype, extra = {}) => ({
  fieldname,
  label,
  fieldtype: 'link',
  options: doctype,
  ...extra,
})
const check = (fieldname, label, def = 0) => ({ fieldname, label, fieldtype: 'check', default: def })
const fiscalYear = (fieldname = 'fiscal_year', label = 'Fiscal Year') => ({
  fieldname,
  label,
  fieldtype: 'fiscal_year',
  default: 'fiscal_year',
})

const asOn = [date('report_date', 'As on', 'today')]
const range = [date('from_date', 'From', 'month_start'), date('to_date', 'To', 'today')]
const fyRange = [date('from_date', 'From', 'fiscal_year_start'), date('to_date', 'To', 'today')]

const PERIODICITY = select(
  'periodicity',
  'Periodicity',
  ['Monthly', 'Quarterly', 'Half-Yearly', 'Yearly'],
  'Monthly',
)

// Financial statements can be driven either by fiscal year or by an explicit date
// range, exactly as on the desk. Fiscal Year is the default because ERPNext resolves
// every period back to a fiscal year anyway — a free date range that strays outside
// one fails with "Date … is not in any active Fiscal Year".
const byFiscalYear = (v) => (v.filter_based_on || 'Fiscal Year') === 'Fiscal Year'
const byDateRange = (v) => !byFiscalYear(v)

const statementFilters = [
  select('filter_based_on', 'Based on', ['Fiscal Year', 'Date Range'], 'Fiscal Year'),
  { ...fiscalYear('from_fiscal_year', 'Start Year'), dependsOn: byFiscalYear },
  { ...fiscalYear('to_fiscal_year', 'End Year'), dependsOn: byFiscalYear },
  { ...date('period_start_date', 'From', 'fiscal_year_start'), dependsOn: byDateRange },
  { ...date('period_end_date', 'To', 'fiscal_year_end'), dependsOn: byDateRange },
  PERIODICITY,
  link('finance_book', 'Finance Book', 'Finance Book'),
  link('cost_center', 'Cost Center', 'Cost Center', { filters: { is_group: 0 } }),
  link('project', 'Project', 'Project'),
  link('presentation_currency', 'Currency', 'Currency'),
  check('accumulated_values', 'Accumulated', 1),
  check('include_default_book_entries', 'Include default book entries', 1),
]

// Profit and Loss adds the view switch and the zero-row toggle the desk report has.
const plFilters = [
  ...statementFilters,
  select('selected_view', 'View', ['Report', 'Growth', 'Margin'], 'Report'),
  check('show_zero_values', 'Show zero values', 0),
]

const statementDefaults = {}

export const REPORTS = [
  // --- Financial Statements ------------------------------------------------
  { key: 'profit-and-loss', title: 'Profit and Loss', report: 'Profit and Loss Statement',
    section: 'Financial Statements', icon: TrendingUp, filters: plFilters, defaults: statementDefaults },
  { key: 'balance-sheet', title: 'Balance Sheet', report: 'Balance Sheet',
    section: 'Financial Statements', icon: Scale, filters: statementFilters, defaults: statementDefaults },
  { key: 'cash-flow', title: 'Cash Flow', report: 'Cash Flow',
    section: 'Financial Statements', icon: Activity, filters: statementFilters, defaults: statementDefaults },
  { key: 'trial-balance', title: 'Trial Balance', report: 'Trial Balance',
    section: 'Financial Statements', icon: Calculator, filters: [fiscalYear(), ...fyRange] },
  { key: 'gross-and-net-profit', title: 'Gross and Net Profit', report: 'Gross and Net Profit Report',
    section: 'Financial Statements', icon: Percent, filters: statementFilters, defaults: statementDefaults },
  { key: 'financial-ratios', title: 'Financial Ratios', report: 'Financial Ratios',
    section: 'Financial Statements', icon: Percent, filters: statementFilters, defaults: statementDefaults },

  // --- Receivables & Payables ---------------------------------------------
  { key: 'accounts-receivable', title: 'Accounts Receivable', report: 'Accounts Receivable',
    section: 'Receivables & Payables', icon: ArrowDownLeft, filters: asOn },
  { key: 'ar-summary', title: 'AR Summary', report: 'Accounts Receivable Summary',
    section: 'Receivables & Payables', icon: Wallet, filters: asOn },
  { key: 'accounts-payable', title: 'Accounts Payable', report: 'Accounts Payable',
    section: 'Receivables & Payables', icon: ArrowUpRight, filters: asOn },
  { key: 'ap-summary', title: 'AP Summary', report: 'Accounts Payable Summary',
    section: 'Receivables & Payables', icon: Wallet, filters: asOn },
  { key: 'customer-ledger-summary', title: 'Customer Ledger Summary', report: 'Customer Ledger Summary',
    section: 'Receivables & Payables', icon: Users, filters: range },
  { key: 'supplier-ledger-summary', title: 'Supplier Ledger Summary', report: 'Supplier Ledger Summary',
    section: 'Receivables & Payables', icon: Truck, filters: range },

  // --- Ledgers ------------------------------------------------------------
  { key: 'general-ledger', title: 'General Ledger', report: 'General Ledger',
    section: 'Ledgers', icon: BookOpen, filters: range },
  { key: 'payment-ledger', title: 'Payment Ledger', report: 'Payment Ledger',
    section: 'Ledgers', icon: Wallet, filters: range },
  { key: 'account-balance', title: 'Account Balance', report: 'Account Balance',
    section: 'Ledgers', icon: Landmark, filters: asOn },
  { key: 'bank-reconciliation', title: 'Bank Reconciliation', report: 'Bank Reconciliation Statement',
    section: 'Ledgers', icon: Landmark,
    filters: [
      link('account', 'Bank Account', 'Account', { filters: { account_type: 'Bank', is_group: 0 } }),
      date('report_date', 'As on', 'today'),
    ] },
  { key: 'trial-balance-for-party', title: 'Trial Balance for Party', report: 'Trial Balance for Party',
    section: 'Ledgers', icon: Calculator, filters: fyRange },

  // --- Sales & Purchases ---------------------------------------------------
  { key: 'sales-register', title: 'Sales Register', report: 'Sales Register',
    section: 'Sales & Purchases', icon: Receipt, filters: range },
  { key: 'purchase-register', title: 'Purchase Register', report: 'Purchase Register',
    section: 'Sales & Purchases', icon: ShoppingBag, filters: range },
  { key: 'item-wise-sales', title: 'Item-wise Sales', report: 'Item-wise Sales Register',
    section: 'Sales & Purchases', icon: Layers, filters: range },
  { key: 'item-wise-purchases', title: 'Item-wise Purchases', report: 'Item-wise Purchase Register',
    section: 'Sales & Purchases', icon: Layers, filters: range },
  { key: 'gross-profit', title: 'Gross Profit', report: 'Gross Profit',
    section: 'Sales & Purchases', icon: Percent,
    filters: [
      ...range,
      select('group_by', 'Group by',
        ['Invoice', 'Item Code', 'Customer', 'Customer Group', 'Item Group', 'Territory', 'Sales Person', 'Project', 'Warehouse'],
        'Invoice'),
    ] },
  { key: 'sales-order-analysis', title: 'Sales Order Analysis', report: 'Sales Order Analysis',
    section: 'Sales & Purchases', icon: Target, filters: range },
  { key: 'purchase-order-analysis', title: 'Purchase Order Analysis', report: 'Purchase Order Analysis',
    section: 'Sales & Purchases', icon: Target, filters: range },
  { key: 'budget-variance', title: 'Budget Variance', report: 'Budget Variance Report',
    section: 'Sales & Purchases', icon: Target,
    filters: [fiscalYear(), PERIODICITY, select('budget_against', 'Budget against', ['Cost Center', 'Project'], 'Cost Center')] },

  // --- Stock ---------------------------------------------------------------
  { key: 'stock-balance', title: 'Stock Balance', report: 'Stock Balance',
    section: 'Stock', icon: Package, filters: range },
  { key: 'stock-ledger', title: 'Stock Ledger', report: 'Stock Ledger',
    section: 'Stock', icon: BookOpen, filters: range },
  { key: 'stock-ageing', title: 'Stock Ageing', report: 'Stock Ageing',
    section: 'Stock', icon: Package,
    filters: [date('to_date', 'As on', 'today'), check('show_warehouse_wise_stock', 'Warehouse-wise')] },
  { key: 'stock-projected-qty', title: 'Stock Projected Qty', report: 'Stock Projected Qty',
    section: 'Stock', icon: Package, filters: [] },
]

export function findReport(key) {
  return REPORTS.find((r) => r.key === key)
}
