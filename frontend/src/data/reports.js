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
// ERPNext renders several of these as MultiSelectList and reads them with `in`, so the
// value has to travel as a list even when only one thing is picked. `asList` marks them;
// buildFilters below does the wrapping.
const multi = (fieldname, label, doctype, extra = {}) => ({
  ...link(fieldname, label, doctype, extra),
  asList: true,
})

const CUSTOMER = (fn = 'party') => multi(fn, 'Customer', 'Customer', { filters: { disabled: 0 } })
const SUPPLIER = (fn = 'party') => multi(fn, 'Supplier', 'Supplier', { filters: { disabled: 0 } })
const COST_CENTER = multi('cost_center', 'Cost Center', 'Cost Center', { filters: { is_group: 0 } })
const PROJECT = multi('project', 'Project', 'Project')
const WAREHOUSE = link('warehouse', 'Warehouse', 'Warehouse', { filters: { is_group: 0 } })
const ITEM = link('item_code', 'Item', 'Item')
const ITEM_GROUP = link('item_group', 'Item Group', 'Item Group')
const BRAND = link('brand', 'Brand', 'Brand')
const MODE_OF_PAYMENT = link('mode_of_payment', 'Mode of Payment', 'Mode of Payment')
const FINANCE_BOOK = link('finance_book', 'Finance Book', 'Finance Book')

/** Build the payload for a report run, honouring `asList`. */
export function buildFilters(cfg, values, extra = {}) {
  const out = { ...(cfg?.defaults || {}) }
  for (const f of cfg?.filters || []) {
    const value = values[f.fieldname]
    if (value === undefined || value === null || value === '') continue
    out[f.fieldname] = f.asList && !Array.isArray(value) ? [value] : value
  }
  return { ...out, ...extra }
}
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
    section: 'Financial Statements', icon: Calculator,
    filters: [fiscalYear(), ...fyRange, COST_CENTER, PROJECT, FINANCE_BOOK,
      check('show_zero_values', 'Show zero values'), check('show_group_accounts', 'Group accounts')] },
  { key: 'gross-and-net-profit', title: 'Gross and Net Profit', report: 'Gross and Net Profit Report',
    section: 'Financial Statements', icon: Percent, filters: statementFilters, defaults: statementDefaults },
  { key: 'financial-ratios', title: 'Financial Ratios', report: 'Financial Ratios',
    section: 'Financial Statements', icon: Percent, filters: statementFilters, defaults: statementDefaults },

  // --- Receivables & Payables ---------------------------------------------
  { key: 'accounts-receivable', title: 'Accounts Receivable', report: 'Accounts Receivable',
    section: 'Receivables & Payables', icon: ArrowDownLeft, defaults: { party_type: 'Customer' },
    filters: [...asOn, CUSTOMER(), link('customer_group', 'Customer Group', 'Customer Group'),
      link('territory', 'Territory', 'Territory'), COST_CENTER, FINANCE_BOOK,
      check('based_on_payment_terms', 'By payment terms'), check('show_future_payments', 'Show future payments')] },
  { key: 'ar-summary', title: 'AR Summary', report: 'Accounts Receivable Summary',
    section: 'Receivables & Payables', icon: Wallet, defaults: { party_type: 'Customer' },
    filters: [...asOn, CUSTOMER(), link('customer_group', 'Customer Group', 'Customer Group'),
      link('territory', 'Territory', 'Territory'), COST_CENTER, check('show_gl_balance', 'Show GL balance')] },
  { key: 'accounts-payable', title: 'Accounts Payable', report: 'Accounts Payable',
    section: 'Receivables & Payables', icon: ArrowUpRight, defaults: { party_type: 'Supplier' },
    filters: [...asOn, SUPPLIER(), link('supplier_group', 'Supplier Group', 'Supplier Group'),
      COST_CENTER, FINANCE_BOOK, check('based_on_payment_terms', 'By payment terms')] },
  { key: 'ap-summary', title: 'AP Summary', report: 'Accounts Payable Summary',
    section: 'Receivables & Payables', icon: Wallet, defaults: { party_type: 'Supplier' },
    filters: [...asOn, SUPPLIER(), link('supplier_group', 'Supplier Group', 'Supplier Group'),
      COST_CENTER, check('show_gl_balance', 'Show GL balance')] },
  { key: 'customer-ledger-summary', title: 'Customer Ledger Summary', report: 'Customer Ledger Summary',
    section: 'Receivables & Payables', icon: Users,
    filters: [...range, link('party', 'Customer', 'Customer', { filters: { disabled: 0 } }),
      link('customer_group', 'Customer Group', 'Customer Group'), link('territory', 'Territory', 'Territory'),
      COST_CENTER, PROJECT] },
  { key: 'supplier-ledger-summary', title: 'Supplier Ledger Summary', report: 'Supplier Ledger Summary',
    section: 'Receivables & Payables', icon: Truck,
    filters: [...range, link('party', 'Supplier', 'Supplier', { filters: { disabled: 0 } }),
      link('supplier_group', 'Supplier Group', 'Supplier Group'), COST_CENTER, PROJECT] },

  // --- Ledgers ------------------------------------------------------------
  { key: 'general-ledger', title: 'General Ledger', report: 'General Ledger',
    section: 'Ledgers', icon: BookOpen,
    filters: [...range, multi('account', 'Account', 'Account', { filters: { is_group: 0 } }),
      select('party_type', 'Party Type', ['', 'Customer', 'Supplier'], ''),
      multi('party', 'Party', 'Customer'),
      link('voucher_no', 'Voucher No', 'GL Entry'), COST_CENTER, PROJECT,
      check('show_opening_entries', 'Show opening entries'),
      check('include_default_book_entries', 'Include default book entries', 1)] },
  // Payment Ledger names its dates differently from every other ledger report.
  { key: 'payment-ledger', title: 'Payment Ledger', report: 'Payment Ledger',
    section: 'Ledgers', icon: Wallet,
    filters: [date('period_start_date', 'From', 'month_start'), date('period_end_date', 'To', 'today'),
      multi('account', 'Account', 'Account', { filters: { is_group: 0 } }),
      select('party_type', 'Party Type', ['', 'Customer', 'Supplier'], ''),
      multi('party', 'Party', 'Customer'), check('group_party', 'Group by party')] },
  { key: 'account-balance', title: 'Account Balance', report: 'Account Balance',
    section: 'Ledgers', icon: Landmark,
    filters: [...asOn, select('root_type', 'Root Type', ['', 'Asset', 'Liability', 'Income', 'Expense', 'Equity'], ''),
      link('account_type', 'Account Type', 'Account Type')] },
  { key: 'bank-reconciliation', title: 'Bank Reconciliation', report: 'Bank Reconciliation Statement',
    section: 'Ledgers', icon: Landmark,
    filters: [
      link('account', 'Bank Account', 'Account', { filters: { account_type: 'Bank', is_group: 0 } }),
      date('report_date', 'As on', 'today'),
    ] },
  { key: 'trial-balance-for-party', title: 'Trial Balance for Party', report: 'Trial Balance for Party',
    section: 'Ledgers', icon: Calculator,
    filters: [...fyRange, select('party_type', 'Party Type', ['Customer', 'Supplier'], 'Customer'),
      multi('party', 'Party', 'Customer'), COST_CENTER, PROJECT] },

  // --- Sales & Purchases ---------------------------------------------------
  { key: 'sales-register', title: 'Sales Register', report: 'Sales Register',
    section: 'Sales & Purchases', icon: Receipt,
    filters: [...range, link('customer', 'Customer', 'Customer', { filters: { disabled: 0 } }),
      link('customer_group', 'Customer Group', 'Customer Group'), MODE_OF_PAYMENT, WAREHOUSE,
      ITEM_GROUP, BRAND, COST_CENTER] },
  { key: 'purchase-register', title: 'Purchase Register', report: 'Purchase Register',
    section: 'Sales & Purchases', icon: ShoppingBag,
    filters: [...range, link('supplier', 'Supplier', 'Supplier', { filters: { disabled: 0 } }),
      link('supplier_group', 'Supplier Group', 'Supplier Group'), MODE_OF_PAYMENT, WAREHOUSE,
      ITEM_GROUP, COST_CENTER] },
  { key: 'item-wise-sales', title: 'Item-wise Sales', report: 'Item-wise Sales Register',
    section: 'Sales & Purchases', icon: Layers,
    filters: [...range, link('customer', 'Customer', 'Customer', { filters: { disabled: 0 } }),
      ITEM, ITEM_GROUP, BRAND, WAREHOUSE, MODE_OF_PAYMENT,
      select('group_by', 'Group by', ['', 'Item', 'Item Group', 'Customer', 'Customer Group', 'Territory', 'Supplier', 'Supplier Group'], '')] },
  { key: 'item-wise-purchases', title: 'Item-wise Purchases', report: 'Item-wise Purchase Register',
    section: 'Sales & Purchases', icon: Layers,
    filters: [...range, link('supplier', 'Supplier', 'Supplier', { filters: { disabled: 0 } }),
      ITEM, ITEM_GROUP, MODE_OF_PAYMENT,
      select('group_by', 'Group by', ['', 'Item', 'Item Group', 'Supplier', 'Supplier Group'], '')] },
  { key: 'gross-profit', title: 'Gross Profit', report: 'Gross Profit',
    section: 'Sales & Purchases', icon: Percent,
    filters: [
      ...range,
      select('group_by', 'Group by',
        ['Invoice', 'Item Code', 'Customer', 'Customer Group', 'Item Group', 'Territory', 'Sales Person', 'Project', 'Warehouse'],
        'Invoice'),
      ITEM_GROUP, WAREHOUSE, COST_CENTER, PROJECT,
      link('sales_person', 'Sales Person', 'Sales Person'),
      check('include_returned_invoices', 'Include returns'),
    ] },
  { key: 'sales-order-analysis', title: 'Sales Order Analysis', report: 'Sales Order Analysis',
    section: 'Sales & Purchases', icon: Target,
    filters: [...range, multi('sales_order', 'Sales Order', 'Sales Order'), WAREHOUSE,
      select('status', 'Status', ['', 'To Deliver and Bill', 'To Bill', 'To Deliver', 'Completed'], ''),
      check('group_by_so', 'Group by order')] },
  { key: 'purchase-order-analysis', title: 'Purchase Order Analysis', report: 'Purchase Order Analysis',
    section: 'Sales & Purchases', icon: Target,
    filters: [...range, multi('name', 'Purchase Order', 'Purchase Order'), PROJECT,
      select('status', 'Status', ['', 'To Receive and Bill', 'To Bill', 'To Receive', 'Completed'], ''),
      check('group_by_po', 'Group by order')] },
  { key: 'budget-variance', title: 'Budget Variance', report: 'Budget Variance Report',
    section: 'Sales & Purchases', icon: Target,
    filters: [fiscalYear(), PERIODICITY, select('budget_against', 'Budget against', ['Cost Center', 'Project'], 'Cost Center')] },

  // --- Stock ---------------------------------------------------------------
  { key: 'stock-balance', title: 'Stock Balance', report: 'Stock Balance',
    section: 'Stock', icon: Package,
    filters: [...range, multi('item_code', 'Item', 'Item'), ITEM_GROUP,
      multi('warehouse', 'Warehouse', 'Warehouse', { filters: { is_group: 0 } }), BRAND,
      check('include_zero_stock_items', 'Include zero stock')] },
  { key: 'stock-ledger', title: 'Stock Ledger', report: 'Stock Ledger',
    section: 'Stock', icon: BookOpen,
    filters: [...range, multi('item_code', 'Item', 'Item'), ITEM_GROUP,
      multi('warehouse', 'Warehouse', 'Warehouse', { filters: { is_group: 0 } }), BRAND,
      link('batch_no', 'Batch', 'Batch'), link('voucher_no', 'Voucher No', 'Stock Ledger Entry'), PROJECT] },
  { key: 'stock-ageing', title: 'Stock Ageing', report: 'Stock Ageing',
    section: 'Stock', icon: Package,
    // `range` is the ageing buckets; the report reads it with .split() and fails on
    // nothing at all, so it always travels with a value.
    filters: [date('to_date', 'As on', 'today'), ITEM, WAREHOUSE, BRAND,
      select('range', 'Ageing buckets', ['30, 60, 90', '30, 60, 90, 120', '7, 14, 30, 60'], '30, 60, 90'),
      check('show_warehouse_wise_stock', 'Warehouse-wise')] },
  { key: 'stock-projected-qty', title: 'Stock Projected Qty', report: 'Stock Projected Qty',
    section: 'Stock', icon: Package, filters: [ITEM, ITEM_GROUP, WAREHOUSE, BRAND] },
]

export function findReport(key) {
  return REPORTS.find((r) => r.key === key)
}
