// Central config: sidebar + generic list + in-app create modal are all driven from here.
import FileText from '~icons/lucide/file-text'
import ShoppingCart from '~icons/lucide/shopping-cart'
import Truck from '~icons/lucide/truck'
import Receipt from '~icons/lucide/receipt'
import ClipboardList from '~icons/lucide/clipboard-list'
import ShoppingBag from '~icons/lucide/shopping-bag'
import PackageCheck from '~icons/lucide/package-check'
import Package from '~icons/lucide/package'
import Repeat from '~icons/lucide/repeat'
import Scale from '~icons/lucide/scale'
import CreditCard from '~icons/lucide/credit-card'
import BookOpen from '~icons/lucide/book-open'
import Send from '~icons/lucide/send'
import Users from '~icons/lucide/users'
import Factory from '~icons/lucide/factory'

export const SECTIONS = ['Selling', 'Buying', 'Inventory', 'Accounts', 'Masters']

const sel = (arr) => arr.map((v) => ({ label: v, value: v }))

// Reusable header fields
const COMPANY = { fieldname: 'company', label: 'Company', fieldtype: 'link', options: 'Company', default: 'company' }
const CUSTOMER = { fieldname: 'customer', label: 'Customer', fieldtype: 'link', options: 'Customer', filters: { disabled: 0 } }
const SUPPLIER = { fieldname: 'supplier', label: 'Supplier', fieldtype: 'link', options: 'Supplier', filters: { disabled: 0 } }
const WAREHOUSE = { fieldname: 'set_warehouse', label: 'Warehouse', fieldtype: 'link', options: 'Warehouse', default: 'warehouse', filters: { is_group: 0 } }

// Reusable child columns
const ITEM_COL = { fieldname: 'item_code', label: 'Item', fieldtype: 'link', options: 'Item', filters: { disabled: 0 }, flex: 2 }
const QTY_COL = { fieldname: 'qty', label: 'Qty', fieldtype: 'float', flex: 1 }
const RATE_COL = { fieldname: 'rate', label: 'Rate', fieldtype: 'currency', flex: 1 }
const wh = (fn, label) => ({ fieldname: fn, label, fieldtype: 'link', options: 'Warehouse', filters: { is_group: 0 }, flex: 1 })
const SALES_ITEMS = { fieldname: 'items', title: 'Items', columns: [ITEM_COL, QTY_COL, RATE_COL] }
const BUY_ITEMS = SALES_ITEMS

export const LISTS = [
  // Selling
  { key: 'quotation', section: 'Selling', title: 'Quotations', doctype: 'Quotation', icon: FileText, orderBy: 'transaction_date desc',
    columns: [ { label: 'Quotation', field: 'name' }, { label: 'Party', field: 'party_name' }, { label: 'Date', field: 'transaction_date', type: 'date' }, { label: 'Status', field: 'status', type: 'status' }, { label: 'Total', field: 'grand_total', type: 'currency' } ],
    create: { doctype: 'Quotation', title: 'New Quotation', label: 'Quotation', child: SALES_ITEMS,
      fields: [ COMPANY, { fieldname: 'quotation_to', label: 'Quotation To', fieldtype: 'select', selectOptions: sel(['Customer', 'Lead']), default: 'Customer' }, { fieldname: 'party_name', label: 'Party', fieldtype: 'link', options: 'Customer' }, { fieldname: 'transaction_date', label: 'Date', fieldtype: 'date', default: 'today' } ] } },
  { key: 'sales-order', section: 'Selling', title: 'Sales Orders', doctype: 'Sales Order', icon: ShoppingCart, orderBy: 'transaction_date desc',
    columns: [ { label: 'Order', field: 'name' }, { label: 'Customer', field: 'customer_name' }, { label: 'Date', field: 'transaction_date', type: 'date' }, { label: 'Status', field: 'status', type: 'status' }, { label: 'Total', field: 'grand_total', type: 'currency' } ],
    create: { doctype: 'Sales Order', title: 'New Sales Order', label: 'Order', child: SALES_ITEMS,
      fields: [ COMPANY, CUSTOMER, { fieldname: 'delivery_date', label: 'Delivery Date', fieldtype: 'date', default: 'today' }, WAREHOUSE ] } },
  { key: 'delivery-note', section: 'Selling', title: 'Delivery Notes', doctype: 'Delivery Note', icon: Truck, orderBy: 'posting_date desc',
    columns: [ { label: 'Delivery Note', field: 'name' }, { label: 'Customer', field: 'customer_name' }, { label: 'Date', field: 'posting_date', type: 'date' }, { label: 'Status', field: 'status', type: 'status' }, { label: 'Total', field: 'grand_total', type: 'currency' } ],
    create: { doctype: 'Delivery Note', title: 'New Delivery Note', label: 'Delivery Note', child: SALES_ITEMS,
      fields: [ COMPANY, CUSTOMER, WAREHOUSE ] } },
  { key: 'sales-invoice', section: 'Selling', title: 'Sales Invoices', doctype: 'Sales Invoice', icon: Receipt, orderBy: 'posting_date desc',
    columns: [ { label: 'Invoice', field: 'name' }, { label: 'Customer', field: 'customer_name' }, { label: 'Date', field: 'posting_date', type: 'date' }, { label: 'Status', field: 'status', type: 'status' }, { label: 'Total', field: 'grand_total', type: 'currency' } ],
    create: { doctype: 'Sales Invoice', title: 'New Sales Invoice', label: 'Invoice', child: SALES_ITEMS,
      fields: [ COMPANY, CUSTOMER, { fieldname: 'due_date', label: 'Due Date', fieldtype: 'date' }, WAREHOUSE ] } },
  // Buying
  { key: 'material-request', section: 'Buying', title: 'Material Requests', doctype: 'Material Request', icon: ClipboardList, orderBy: 'transaction_date desc',
    columns: [ { label: 'Request', field: 'name' }, { label: 'Type', field: 'material_request_type', type: 'kind' }, { label: 'Date', field: 'transaction_date', type: 'date' }, { label: 'Status', field: 'status', type: 'status' } ],
    create: { doctype: 'Material Request', title: 'New Material Request', label: 'Request',
      child: { fieldname: 'items', title: 'Items', columns: [ ITEM_COL, QTY_COL, wh('warehouse', 'For Warehouse'), { fieldname: 'schedule_date', label: 'Required By', fieldtype: 'date', flex: 1 } ] },
      fields: [ COMPANY, { fieldname: 'material_request_type', label: 'Type', fieldtype: 'select', selectOptions: sel(['Purchase', 'Material Transfer', 'Material Issue', 'Manufacture', 'Customer Provided']), default: 'Purchase' }, { fieldname: 'schedule_date', label: 'Required By', fieldtype: 'date', default: 'today' } ] } },
  { key: 'purchase-order', section: 'Buying', title: 'Purchase Orders', doctype: 'Purchase Order', icon: ShoppingBag, orderBy: 'transaction_date desc',
    columns: [ { label: 'Order', field: 'name' }, { label: 'Supplier', field: 'supplier_name' }, { label: 'Date', field: 'transaction_date', type: 'date' }, { label: 'Status', field: 'status', type: 'status' }, { label: 'Total', field: 'grand_total', type: 'currency' } ],
    create: { doctype: 'Purchase Order', title: 'New Purchase Order', label: 'Order', child: BUY_ITEMS,
      fields: [ COMPANY, SUPPLIER, { fieldname: 'schedule_date', label: 'Required By', fieldtype: 'date', default: 'today' }, WAREHOUSE ] } },
  { key: 'purchase-receipt', section: 'Buying', title: 'Purchase Receipts', doctype: 'Purchase Receipt', icon: PackageCheck, orderBy: 'posting_date desc',
    columns: [ { label: 'Receipt', field: 'name' }, { label: 'Supplier', field: 'supplier_name' }, { label: 'Date', field: 'posting_date', type: 'date' }, { label: 'Status', field: 'status', type: 'status' }, { label: 'Total', field: 'grand_total', type: 'currency' } ],
    create: { doctype: 'Purchase Receipt', title: 'New Purchase Receipt', label: 'Receipt', child: BUY_ITEMS,
      fields: [ COMPANY, SUPPLIER, WAREHOUSE ] } },
  { key: 'purchase-invoice', section: 'Buying', title: 'Purchase Invoices', doctype: 'Purchase Invoice', icon: FileText, orderBy: 'posting_date desc',
    columns: [ { label: 'Invoice', field: 'name' }, { label: 'Supplier', field: 'supplier_name' }, { label: 'Date', field: 'posting_date', type: 'date' }, { label: 'Status', field: 'status', type: 'status' }, { label: 'Total', field: 'grand_total', type: 'currency' } ],
    create: { doctype: 'Purchase Invoice', title: 'New Purchase Invoice', label: 'Invoice', child: BUY_ITEMS,
      fields: [ COMPANY, SUPPLIER, WAREHOUSE ] } },
  // Inventory
  { key: 'item', section: 'Inventory', title: 'Items', doctype: 'Item', icon: Package, orderBy: 'modified desc',
    columns: [ { label: 'Item Code', field: 'name' }, { label: 'Name', field: 'item_name' }, { label: 'Group', field: 'item_group' }, { label: 'UOM', field: 'stock_uom' } ],
    create: { doctype: 'Item', title: 'New Item', label: 'Item',
      fields: [ { fieldname: 'item_code', label: 'Item Code', fieldtype: 'data' }, { fieldname: 'item_name', label: 'Item Name', fieldtype: 'data' }, { fieldname: 'item_group', label: 'Item Group', fieldtype: 'link', options: 'Item Group' }, { fieldname: 'stock_uom', label: 'Default UOM', fieldtype: 'link', options: 'UOM' } ] } },
  { key: 'stock-entry', section: 'Inventory', title: 'Stock Entries', doctype: 'Stock Entry', icon: Repeat, orderBy: 'posting_date desc',
    columns: [ { label: 'Entry', field: 'name' }, { label: 'Type', field: 'stock_entry_type', type: 'kind' }, { label: 'Date', field: 'posting_date', type: 'date' }, { label: 'State', field: 'docstatus', type: 'docstatus' } ],
    create: { doctype: 'Stock Entry', title: 'New Stock Entry', label: 'Entry',
      child: { fieldname: 'items', title: 'Items', columns: [ ITEM_COL, QTY_COL, wh('s_warehouse', 'Source'), wh('t_warehouse', 'Target') ] },
      fields: [ COMPANY, { fieldname: 'stock_entry_type', label: 'Type', fieldtype: 'select', selectOptions: sel(['Material Issue', 'Material Receipt', 'Material Transfer', 'Repack']), default: 'Material Receipt' } ] } },
  { key: 'stock-reconciliation', section: 'Inventory', title: 'Stock Reconciliations', doctype: 'Stock Reconciliation', icon: Scale, orderBy: 'posting_date desc',
    columns: [ { label: 'Reconciliation', field: 'name' }, { label: 'Purpose', field: 'purpose', type: 'kind' }, { label: 'Date', field: 'posting_date', type: 'date' }, { label: 'State', field: 'docstatus', type: 'docstatus' } ],
    create: { doctype: 'Stock Reconciliation', title: 'New Stock Reconciliation', label: 'Reconciliation',
      child: { fieldname: 'items', title: 'Items', columns: [ ITEM_COL, wh('warehouse', 'Warehouse'), QTY_COL, { fieldname: 'valuation_rate', label: 'Rate', fieldtype: 'currency', flex: 1 } ] },
      fields: [ COMPANY, { fieldname: 'purpose', label: 'Purpose', fieldtype: 'select', selectOptions: sel(['Stock Reconciliation', 'Opening Stock']), default: 'Stock Reconciliation' } ] } },
  // Accounts
  { key: 'payment-entry', section: 'Accounts', title: 'Payment Entries', doctype: 'Payment Entry', icon: CreditCard, orderBy: 'posting_date desc', currencyField: 'paid_to_account_currency', special: 'payment',
    columns: [ { label: 'Payment', field: 'name' }, { label: 'Type', field: 'payment_type', type: 'kind' }, { label: 'Party', field: 'party_name' }, { label: 'Date', field: 'posting_date', type: 'date' }, { label: 'State', field: 'docstatus', type: 'docstatus' }, { label: 'Amount', field: 'paid_amount', type: 'currency' } ] },
  { key: 'journal-entry', section: 'Accounts', title: 'Journal Entries', doctype: 'Journal Entry', icon: BookOpen, orderBy: 'posting_date desc', currencyField: '',
    columns: [ { label: 'Entry', field: 'name' }, { label: 'Type', field: 'voucher_type', type: 'kind' }, { label: 'Date', field: 'posting_date', type: 'date' }, { label: 'State', field: 'docstatus', type: 'docstatus' }, { label: 'Debit', field: 'total_debit', type: 'currency' } ],
    create: { doctype: 'Journal Entry', title: 'New Journal Entry', label: 'Journal',
      child: { fieldname: 'accounts', title: 'Accounting Entries', columns: [ { fieldname: 'account', label: 'Account', fieldtype: 'link', options: 'Account', filters: { is_group: 0 }, flex: 2 }, { fieldname: 'debit_in_account_currency', label: 'Debit', fieldtype: 'currency', flex: 1 }, { fieldname: 'credit_in_account_currency', label: 'Credit', fieldtype: 'currency', flex: 1 } ] },
      fields: [ COMPANY, { fieldname: 'voucher_type', label: 'Type', fieldtype: 'select', selectOptions: sel(['Journal Entry', 'Bank Entry', 'Cash Entry', 'Contra Entry', 'Credit Note', 'Debit Note']), default: 'Journal Entry' }, { fieldname: 'posting_date', label: 'Date', fieldtype: 'date', default: 'today' } ] } },
]

// Payment Request is the front door for every payment: nothing is paid directly, it is
// requested, sent for approval, and only then turned into a Payment Entry.
LISTS.push(
  { key: 'payment-request', section: 'Accounts', title: 'Payment Requests', doctype: 'Payment Request', icon: Send, orderBy: 'creation desc', currencyField: 'currency', special: 'payment-request',
    columns: [
      { label: 'Request', field: 'name' },
      { label: 'Party', field: 'party_name' },
      { label: 'Against', field: 'reference_name' },
      { label: 'Mode', field: 'mode_of_payment', type: 'kind' },
      { label: 'Status', field: 'status', type: 'status' },
      { label: 'Amount', field: 'grand_total', type: 'currency' },
    ] },
  // Masters — the compliance fields live on Customer as custom fields (see kamil/setup.py).
  { key: 'customer', section: 'Masters', title: 'Customers', doctype: 'Customer', icon: Users, orderBy: 'modified desc', currencyField: 'default_currency',
    columns: [
      { label: 'Customer', field: 'name' },
      { label: 'Group', field: 'customer_group' },
      { label: 'Tax ID', field: 'tax_id' },
      { label: 'Approval', field: 'workflow_state', type: 'status' },
    ],
    create: { doctype: 'Customer', title: 'New Customer', label: 'Customer',
      fields: [
        { fieldname: 'customer_name', label: 'Customer Name', fieldtype: 'data' },
        { fieldname: 'customer_group', label: 'Customer Group', fieldtype: 'link', options: 'Customer Group' },
        { fieldname: 'territory', label: 'Territory', fieldtype: 'link', options: 'Territory' },
        { fieldname: 'tax_id', label: 'Tax ID / PIN', fieldtype: 'data' },
        { fieldname: 'kamil_license_number', label: 'License Number', fieldtype: 'data' },
        { fieldname: 'kamil_license_expiry', label: 'License Expiry', fieldtype: 'date' },
        { fieldname: 'kamil_postal_address', label: 'Postal Address', fieldtype: 'data' },
      ] } },
  { key: 'supplier', section: 'Masters', title: 'Suppliers', doctype: 'Supplier', icon: Factory, orderBy: 'modified desc', currencyField: 'default_currency',
    columns: [
      { label: 'Supplier', field: 'name' },
      { label: 'Group', field: 'supplier_group' },
      { label: 'Tax ID', field: 'tax_id' },
    ],
    create: { doctype: 'Supplier', title: 'New Supplier', label: 'Supplier',
      fields: [
        { fieldname: 'supplier_name', label: 'Supplier Name', fieldtype: 'data' },
        { fieldname: 'supplier_group', label: 'Supplier Group', fieldtype: 'link', options: 'Supplier Group' },
        { fieldname: 'tax_id', label: 'Tax ID / PIN', fieldtype: 'data' },
      ] } },
)

export function findList(key) {
  return LISTS.find((l) => l.key === key)
}

/** The list config that renders a given DocType — used to route notifications. */
export function findListByDoctype(doctype) {
  return LISTS.find((l) => l.doctype === doctype)
}
