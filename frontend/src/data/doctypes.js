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
import Car from '~icons/lucide/car'
import Coins from '~icons/lucide/coins'
import Banknote from '~icons/lucide/banknote'
import FileSpreadsheet from '~icons/lucide/file-spreadsheet'
import Layers3 from '~icons/lucide/layers-3'
import ClipboardCheck from '~icons/lucide/clipboard-check'
import IdCard from '~icons/lucide/id-card'
import UserCheck from '~icons/lucide/user-check'

export const SECTIONS = ['Selling', 'Buying', 'Inventory', 'Accounts', 'Payroll', 'Masters']

const sel = (arr) => arr.map((v) => ({ label: v, value: v }))

// Reusable header fields
const COMPANY = { fieldname: 'company', label: 'Company', fieldtype: 'link', options: 'Company', default: 'company' }
const CUSTOMER = { fieldname: 'customer', label: 'Customer', fieldtype: 'link', options: 'Customer', filters: { disabled: 0 } }
const SUPPLIER = { fieldname: 'supplier', label: 'Supplier', fieldtype: 'link', options: 'Supplier', filters: { disabled: 0 } }
const WAREHOUSE = { fieldname: 'set_warehouse', label: 'Warehouse', fieldtype: 'link', options: 'Warehouse', default: 'warehouse', filters: { is_group: 0 } }
// Picking a vehicle fills plate, trailer, driver, transporter, warehouse and the
// compartment rows server-side (kamil.api._fill_from_vehicle).
const VEHICLE = { fieldname: 'custom_vehicle', label: 'Vehicle', fieldtype: 'link', options: 'Vehicle' }

// Reusable child columns
const ITEM_COL = { fieldname: 'item_code', label: 'Item', fieldtype: 'link', options: 'Item', filters: { disabled: 0 }, flex: 2 }
const QTY_COL = { fieldname: 'qty', label: 'Qty', fieldtype: 'float', flex: 1 }
const RATE_COL = { fieldname: 'rate', label: 'Rate', fieldtype: 'currency', flex: 1 }
const wh = (fn, label) => ({ fieldname: fn, label, fieldtype: 'link', options: 'Warehouse', filters: { is_group: 0 }, flex: 1 })
const AMOUNT_COL = { fieldname: 'amount', label: 'Amount', fieldtype: 'amount', flex: 1 }
// UOM and warehouse are filled from the item when one is picked, and stay editable.
const UOM_COL = { fieldname: 'uom', label: 'UOM', fieldtype: 'link', options: 'UOM', flex: 1 }
const ITEM_WH_COL = { ...wh('warehouse', 'Warehouse'), flex: 1 }
const SALES_ITEMS = { fieldname: 'items', title: 'Items', columns: [ITEM_COL, QTY_COL, UOM_COL, ITEM_WH_COL, RATE_COL, AMOUNT_COL] }
const BUY_ITEMS = SALES_ITEMS

export const LISTS = [
  // Selling — invoices carry the stock movement themselves (update_stock).
  { key: 'sales-order', section: 'Selling', title: 'Sales Orders', doctype: 'Sales Order', icon: ShoppingCart, orderBy: 'modified desc',
    columns: [ { label: 'Order', field: 'name' }, { label: 'Customer', field: 'customer_name' }, { label: 'Date', field: 'transaction_date', type: 'date' }, { label: 'Status', field: 'status', type: 'status' }, { label: 'Total', field: 'grand_total', type: 'currency' }, { label: 'Currency', field: 'currency' }, { label: 'Modified', field: 'modified', type: 'ago' } ],
    create: { doctype: 'Sales Order', title: 'New Sales Order', label: 'Order', child: SALES_ITEMS,
      fields: [ COMPANY, CUSTOMER, { fieldname: 'delivery_date', label: 'Delivery Date', fieldtype: 'date', default: 'today' }, VEHICLE, WAREHOUSE , { fieldname: 'currency', label: 'Currency', fieldtype: 'link', options: 'Currency' } ] } },
  { key: 'sales-invoice', section: 'Selling', title: 'Sales Invoices', doctype: 'Sales Invoice', icon: Receipt, orderBy: 'modified desc',
    columns: [ { label: 'Invoice', field: 'name' }, { label: 'Customer', field: 'customer_name' }, { label: 'Date', field: 'posting_date', type: 'date' }, { label: 'Status', field: 'status', type: 'status' }, { label: 'Total', field: 'grand_total', type: 'currency' }, { label: 'Currency', field: 'currency' }, { label: 'Modified', field: 'modified', type: 'ago' } ],
    create: { doctype: 'Sales Invoice', title: 'New Sales Invoice', label: 'Invoice', child: SALES_ITEMS,
      fields: [ COMPANY, CUSTOMER, { fieldname: 'due_date', label: 'Due Date', fieldtype: 'date' }, VEHICLE, WAREHOUSE, { fieldname: 'currency', label: 'Currency', fieldtype: 'link', options: 'Currency' },
        { fieldname: 'custom_bol', label: 'Bill of Lading', fieldtype: 'attach' },
        { fieldname: 'update_stock', label: 'Update stock', fieldtype: 'check', default: 1 } ] } },
  // Buying
  { key: 'purchase-order', section: 'Buying', title: 'Purchase Orders', doctype: 'Purchase Order', icon: ShoppingBag, orderBy: 'modified desc',
    columns: [ { label: 'Order', field: 'name' }, { label: 'Supplier', field: 'supplier_name' }, { label: 'Date', field: 'transaction_date', type: 'date' }, { label: 'Status', field: 'status', type: 'status' }, { label: 'Total', field: 'grand_total', type: 'currency' }, { label: 'Currency', field: 'currency' }, { label: 'Modified', field: 'modified', type: 'ago' } ],
    create: { doctype: 'Purchase Order', title: 'New Purchase Order', label: 'Order', child: BUY_ITEMS,
      fields: [ COMPANY, SUPPLIER, { fieldname: 'schedule_date', label: 'Required By', fieldtype: 'date', default: 'today' }, WAREHOUSE , { fieldname: 'currency', label: 'Currency', fieldtype: 'link', options: 'Currency' } ] } },
  { key: 'purchase-invoice', section: 'Buying', title: 'Purchase Invoices', doctype: 'Purchase Invoice', icon: FileText, orderBy: 'modified desc',
    columns: [ { label: 'Invoice', field: 'name' }, { label: 'Supplier', field: 'supplier_name' }, { label: 'Bill No', field: 'bill_no' }, { label: 'Date', field: 'posting_date', type: 'date' }, { label: 'Status', field: 'status', type: 'status' }, { label: 'Total', field: 'grand_total', type: 'currency' }, { label: 'Currency', field: 'currency' }, { label: 'Modified', field: 'modified', type: 'ago' } ],
    create: { doctype: 'Purchase Invoice', title: 'New Purchase Invoice', label: 'Invoice', child: BUY_ITEMS,
      fields: [ COMPANY, SUPPLIER, WAREHOUSE, { fieldname: 'currency', label: 'Currency', fieldtype: 'link', options: 'Currency' },
        { fieldname: 'bill_no', label: 'Supplier Invoice No', fieldtype: 'data' },
        { fieldname: 'bill_date', label: 'Supplier Invoice Date', fieldtype: 'date' },
        { fieldname: 'custom_supplier_invoice', label: 'Supplier Invoice (attachment)', fieldtype: 'attach' },
        { fieldname: 'update_stock', label: 'Update stock', fieldtype: 'check', default: 1 } ] } },
  // Inventory
  { key: 'item', section: 'Inventory', title: 'Items', doctype: 'Item', icon: Package, orderBy: 'modified desc',
    reportTabs: [
      { label: 'Stock Balance', report: 'stock-balance' },
      { label: 'Stock Ledger', report: 'stock-ledger' },
    ],
    view: [
      { label: 'Item Code', field: 'name' },
      { label: 'Name', field: 'item_name' },
      { label: 'Group', field: 'item_group' },
      { label: 'Stock UOM', field: 'stock_uom' },
      { label: 'Description', field: 'description' },
      { label: 'Brand', field: 'brand' },
      { label: 'Valuation Rate', field: 'valuation_rate', type: 'currency' },
      { label: 'Standard Rate', field: 'standard_rate', type: 'currency' },
      { label: 'Last Purchase Rate', field: 'last_purchase_rate', type: 'currency' },
      { label: 'Safety Stock', field: 'safety_stock' },
      { label: 'Stock Item', field: 'is_stock_item', type: 'kind' },
      { label: 'Disabled', field: 'disabled', type: 'kind' },
    ],
    columns: [ { label: 'Item Code', field: 'name' }, { label: 'Name', field: 'item_name' }, { label: 'Group', field: 'item_group' }, { label: 'UOM', field: 'stock_uom' }, { label: 'Modified', field: 'modified', type: 'ago' } ],
    create: { doctype: 'Item', title: 'New Item', label: 'Item',
      fields: [ { fieldname: 'item_code', label: 'Item Code', fieldtype: 'data' }, { fieldname: 'item_name', label: 'Item Name', fieldtype: 'data' }, { fieldname: 'item_group', label: 'Item Group', fieldtype: 'link', options: 'Item Group' }, { fieldname: 'stock_uom', label: 'Default UOM', fieldtype: 'link', options: 'UOM' } ] } },
  { key: 'stock-entry', section: 'Inventory', title: 'Stock Entries', doctype: 'Stock Entry', icon: Repeat, orderBy: 'modified desc',
    columns: [ { label: 'Entry', field: 'name' }, { label: 'Type', field: 'stock_entry_type', type: 'kind' }, { label: 'Date', field: 'posting_date', type: 'date' }, { label: 'State', field: 'docstatus', type: 'docstatus' }, { label: 'Modified', field: 'modified', type: 'ago' } ],
    create: { doctype: 'Stock Entry', title: 'New Stock Entry', label: 'Entry',
      child: { fieldname: 'items', title: 'Items', columns: [ ITEM_COL, QTY_COL, wh('s_warehouse', 'Source'), wh('t_warehouse', 'Target') ] },
      fields: [ COMPANY, { fieldname: 'stock_entry_type', label: 'Type', fieldtype: 'select', selectOptions: sel(['Material Issue', 'Material Receipt', 'Material Transfer', 'Repack']), default: 'Material Receipt' } ] } },
  { key: 'stock-reconciliation', section: 'Inventory', title: 'Stock Reconciliations', doctype: 'Stock Reconciliation', icon: Scale, orderBy: 'modified desc',
    columns: [ { label: 'Reconciliation', field: 'name' }, { label: 'Purpose', field: 'purpose', type: 'kind' }, { label: 'Date', field: 'posting_date', type: 'date' }, { label: 'State', field: 'docstatus', type: 'docstatus' }, { label: 'Modified', field: 'modified', type: 'ago' } ],
    create: { doctype: 'Stock Reconciliation', title: 'New Stock Reconciliation', label: 'Reconciliation',
      child: { fieldname: 'items', title: 'Items', columns: [ ITEM_COL, wh('warehouse', 'Warehouse'), QTY_COL, { fieldname: 'valuation_rate', label: 'Rate', fieldtype: 'currency', flex: 1 } ] },
      fields: [ COMPANY, { fieldname: 'purpose', label: 'Purpose', fieldtype: 'select', selectOptions: sel(['Stock Reconciliation', 'Opening Stock']), default: 'Stock Reconciliation' } ] } },
  // Accounts
  { key: 'payment-request', section: 'Accounts', title: 'Payment Requests', doctype: 'Payment Request', icon: Send, orderBy: 'modified desc', currencyField: 'currency', special: 'payment-request',
    columns: [
      { label: 'Request', field: 'name' },
      { label: 'Party', field: 'party_name' },
      { label: 'Against', field: 'reference_name' },
      { label: 'Mode', field: 'mode_of_payment', type: 'kind' },
      { label: 'Status', field: 'status', type: 'status' },
      { label: 'Amount', field: 'grand_total', type: 'currency' },
      { label: 'Modified', field: 'modified', type: 'ago' },
    ] },
  { key: 'payment-entry', section: 'Accounts', title: 'Payment Entries', doctype: 'Payment Entry', icon: CreditCard, orderBy: 'modified desc', currencyField: 'paid_to_account_currency', special: 'payment',
    columns: [ { label: 'Payment', field: 'name' }, { label: 'Type', field: 'payment_type', type: 'kind' }, { label: 'Party', field: 'party_name' }, { label: 'Date', field: 'posting_date', type: 'date' }, { label: 'State', field: 'docstatus', type: 'docstatus' }, { label: 'Amount', field: 'paid_amount', type: 'currency' }, { label: 'Modified', field: 'modified', type: 'ago' } ],
    // Used when a payment is raised off an invoice: the mapped values open here.
    create: { doctype: 'Payment Entry', title: 'Payment Entry', label: 'Payment',
      fields: [
        COMPANY,
        { fieldname: 'payment_type', label: 'Type', fieldtype: 'select', selectOptions: sel(['Receive', 'Pay', 'Internal Transfer']), default: 'Receive' },
        { fieldname: 'posting_date', label: 'Posting Date', fieldtype: 'date', default: 'today' },
        { fieldname: 'party_type', label: 'Party Type', fieldtype: 'select', selectOptions: sel(['Customer', 'Supplier']) },
        { fieldname: 'party', label: 'Party', fieldtype: 'data' },
        { fieldname: 'paid_from', label: 'Paid From', fieldtype: 'link', options: 'Account', filters: { is_group: 0 } },
        { fieldname: 'paid_to', label: 'Paid To', fieldtype: 'link', options: 'Account', filters: { is_group: 0 } },
        { fieldname: 'paid_amount', label: 'Amount', fieldtype: 'currency' },
        { fieldname: 'received_amount', label: 'Received Amount', fieldtype: 'currency' },
        { fieldname: 'mode_of_payment', label: 'Mode of Payment', fieldtype: 'link', options: 'Mode of Payment' },
        { fieldname: 'reference_no', label: 'Reference No', fieldtype: 'data' },
        { fieldname: 'reference_date', label: 'Reference Date', fieldtype: 'date' },
      ] } },
  { key: 'currency-exchange', section: 'Accounts', title: 'Currency Exchange', doctype: 'Currency Exchange', icon: Coins, orderBy: 'modified desc', currencyField: '',
    view: [
      { label: 'Rate', field: 'name' },
      { label: 'Date', field: 'date', type: 'date' },
      { label: 'From', field: 'from_currency' },
      { label: 'To', field: 'to_currency' },
      { label: 'Exchange Rate', field: 'exchange_rate' },
      { label: 'For Buying', field: 'for_buying', type: 'kind' },
      { label: 'For Selling', field: 'for_selling', type: 'kind' },
      { label: 'Modified', field: 'modified', type: 'ago' },
    ],
    columns: [
      { label: 'Rate', field: 'name' },
      { label: 'Date', field: 'date', type: 'date' },
      { label: 'From', field: 'from_currency' },
      { label: 'To', field: 'to_currency' },
      { label: 'Rate', field: 'exchange_rate' },
      { label: 'Modified', field: 'modified', type: 'ago' },
    ],
    create: { doctype: 'Currency Exchange', title: 'New Exchange Rate', label: 'Rate',
      fields: [
        { fieldname: 'date', label: 'Date', fieldtype: 'date', default: 'today' },
        { fieldname: 'from_currency', label: 'From Currency', fieldtype: 'link', options: 'Currency', default: 'USD' },
        { fieldname: 'to_currency', label: 'To Currency', fieldtype: 'link', options: 'Currency' },
        { fieldname: 'exchange_rate', label: 'Exchange Rate', fieldtype: 'float' },
        { fieldname: 'for_buying', label: 'For Buying', fieldtype: 'check', default: 1 },
        { fieldname: 'for_selling', label: 'For Selling', fieldtype: 'check', default: 1 },
      ] } },
  { key: 'journal-entry', section: 'Accounts', title: 'Journal Entries', doctype: 'Journal Entry', icon: BookOpen, orderBy: 'modified desc', currencyField: '',
    columns: [ { label: 'Entry', field: 'name' }, { label: 'Type', field: 'voucher_type', type: 'kind' }, { label: 'Date', field: 'posting_date', type: 'date' }, { label: 'State', field: 'docstatus', type: 'docstatus' }, { label: 'Debit', field: 'total_debit', type: 'currency' }, { label: 'Modified', field: 'modified', type: 'ago' } ],
    create: { doctype: 'Journal Entry', title: 'New Journal Entry', label: 'Journal',
      child: { fieldname: 'accounts', title: 'Accounting Entries', columns: [ { fieldname: 'account', label: 'Account', fieldtype: 'link', options: 'Account', filters: { is_group: 0 }, flex: 2 }, { fieldname: 'debit_in_account_currency', label: 'Debit', fieldtype: 'currency', flex: 1 }, { fieldname: 'credit_in_account_currency', label: 'Credit', fieldtype: 'currency', flex: 1 } ] },
      fields: [ COMPANY, { fieldname: 'voucher_type', label: 'Type', fieldtype: 'select', selectOptions: sel(['Journal Entry', 'Bank Entry', 'Cash Entry', 'Contra Entry', 'Credit Note', 'Debit Note']), default: 'Journal Entry' }, { fieldname: 'posting_date', label: 'Date', fieldtype: 'date', default: 'today' } ] } },
]

// Payment Request is the front door for every payment: nothing is paid directly, it is
// requested, sent for approval, and only then turned into a Payment Entry.
LISTS.push(
  // Masters — the compliance fields live on Customer as custom fields (see kamil/setup.py).
  // Fields mirror the live Customer doctype: customer_type, the name parts, contact
  // details and `custom_verfication_status` (spelling is theirs) all already exist
  // there. The kamil_* compliance fields are the only ones this app adds.
  { key: 'customer', section: 'Masters', title: 'Customers', doctype: 'Customer', icon: Users, orderBy: 'modified desc', currencyField: 'default_currency',
    // What is owed and the ledger behind it, without leaving the list. Clicking a
    // party in either opens that customer's general ledger.
    reportTabs: [
      { label: 'AR', report: 'ar-summary', partyType: 'Customer' },
      { label: 'GL', report: 'general-ledger', partyType: 'Customer' },
    ],
    view: [
      { label: 'Customer', field: 'name' },
      { label: 'Type', field: 'customer_type', type: 'kind' },
      { label: 'Group', field: 'customer_group' },
      { label: 'Territory', field: 'territory' },
      { label: 'Currency', field: 'default_currency' },
      { label: 'Price List', field: 'default_price_list' },
      { label: 'Tax ID', field: 'tax_id' },
      { label: 'License No', field: 'kamil_license_number' },
      { label: 'License Expiry', field: 'kamil_license_expiry', type: 'date' },
      { label: 'Postal Address', field: 'kamil_postal_address' },
      { label: 'Mobile', field: 'mobile_no' },
      { label: 'Email', field: 'email_id' },
      { label: 'Primary Address', field: 'primary_address' },
      { label: 'Payment Terms', field: 'payment_terms' },
      { label: 'Verification', field: 'custom_verfication_status', type: 'status' },
      { label: 'Approval', field: 'workflow_state', type: 'status' },
      { label: 'Disabled', field: 'disabled', type: 'kind' },
    ],
    columns: [
      { label: 'Customer', field: 'name' },
      { label: 'Type', field: 'customer_type', type: 'kind' },
      { label: 'Group', field: 'customer_group' },
      { label: 'Tax ID', field: 'tax_id' },
      { label: 'Verification', field: 'custom_verfication_status', type: 'status' },
      { label: 'Approval', field: 'workflow_state', type: 'status' },
      { label: 'Modified', field: 'modified', type: 'ago' },
    ],
    // The whole customer record in one modal. Fields a site does not have (the
    // verification status is a local customisation) are dropped by CreateDialog,
    // which asks the server what really exists before rendering.
    create: { doctype: 'Customer', title: 'New Customer', label: 'Customer',
      // Creates the contact and the address alongside the customer.
      method: 'kamil.api.create_customer',
      fields: [
        { section: 'Customer', fieldname: 'customer_name', label: 'Customer Name', fieldtype: 'data' },
        { section: 'Customer', fieldname: 'customer_type', label: 'Type', fieldtype: 'select', selectOptions: sel(['Company', 'Individual', 'Proprietorship', 'Partnership']), default: 'Company' },
        { section: 'Customer', fieldname: 'customer_group', label: 'Customer Group', fieldtype: 'link', options: 'Customer Group' },
        { section: 'Customer', fieldname: 'territory', label: 'Territory', fieldtype: 'link', options: 'Territory' },
        { section: 'Customer', fieldname: 'default_currency', label: 'Currency', fieldtype: 'link', options: 'Currency' },
        { section: 'Customer', fieldname: 'default_price_list', label: 'Price List', fieldtype: 'link', options: 'Price List' },
        // Contact and address live in their own doctypes; `virtual` marks the fields
        // that are not on Customer itself, so they skip the field-exists check.
        { section: 'Contact', fieldname: 'contact_first_name', label: 'Contact First Name', fieldtype: 'data', virtual: true },
        { section: 'Contact', fieldname: 'contact_last_name', label: 'Contact Last Name', fieldtype: 'data', virtual: true },
        { section: 'Contact', fieldname: 'contact_mobile', label: 'Mobile', fieldtype: 'data', virtual: true },
        { section: 'Contact', fieldname: 'contact_email', label: 'Email', fieldtype: 'data', virtual: true },
        { section: 'Address', fieldname: 'address_line1', label: 'Address Line 1', fieldtype: 'data', virtual: true },
        { section: 'Address', fieldname: 'address_line2', label: 'Address Line 2', fieldtype: 'data', virtual: true },
        { section: 'Address', fieldname: 'address_city', label: 'City / Town', fieldtype: 'data', virtual: true },
        { section: 'Address', fieldname: 'address_country', label: 'Country', fieldtype: 'link', options: 'Country', virtual: true },
        { section: 'Address', fieldname: 'kamil_postal_address', label: 'Postal Address', fieldtype: 'data' },
        // Statutory identity — what the licence and tax checks are done against.
        { section: 'Statutory & KYC', fieldname: 'tax_id', label: 'Tax ID / PIN', fieldtype: 'data' },
        { section: 'Statutory & KYC', fieldname: 'kamil_license_number', label: 'License Number', fieldtype: 'data' },
        { section: 'Statutory & KYC', fieldname: 'kamil_license_expiry', label: 'License Expiry', fieldtype: 'date' },
        // Options come from the site: this is a local customisation, not ours.
        { section: 'Statutory & KYC', fieldname: 'custom_verfication_status', label: 'Verification Status', fieldtype: 'select' },
        { section: 'KYC Documents', fieldname: 'kamil_license_file', label: 'Trading / Business License', fieldtype: 'attach' },
        { section: 'KYC Documents', fieldname: 'kamil_certificate_of_incorporation', label: 'Certificate of Incorporation', fieldtype: 'attach' },
        { section: 'KYC Documents', fieldname: 'kamil_cr12', label: 'CR12', fieldtype: 'attach' },
        { section: 'Selling', fieldname: 'payment_terms', label: 'Payment Terms', fieldtype: 'link', options: 'Payment Terms Template' },
        { section: 'Selling', fieldname: 'default_sales_partner', label: 'Sales Partner', fieldtype: 'link', options: 'Sales Partner' },
        { section: 'Selling', fieldname: 'so_required', label: 'Sales Order required before invoicing', fieldtype: 'check' },
        { section: 'Selling', fieldname: 'dn_required', label: 'Delivery Note required before invoicing', fieldtype: 'check' },
      ] } },
  // Fleet. Vehicle is named after its license plate, so `name` is the plate itself.
  // Fleet. Vehicle is named after its license plate, so `name` is the plate itself.
  // Fuel, mileage and valuation are not tracked here — they belong on the transport
  // documents — so those fields are hidden on the doctype too (see kamil/setup.py).
  // People. Employees and sales people are masters the fleet and selling flows point at.
  // Payroll. These live in HRMS; on a site without it the permission check hides them.
  { key: 'payroll-entry', section: 'Payroll', title: 'Payroll Entries', doctype: 'Payroll Entry', icon: Banknote, orderBy: 'modified desc',
    view: [
      { label: 'Entry', field: 'name' },
      { label: 'Company', field: 'company' },
      { label: 'Start Date', field: 'start_date', type: 'date' },
      { label: 'End Date', field: 'end_date', type: 'date' },
      { label: 'Payroll Frequency', field: 'payroll_frequency', type: 'kind' },
      { label: 'Payment Account', field: 'payment_account' },
      { label: 'Cost Center', field: 'cost_center' },
      { label: 'Status', field: 'status', type: 'status' },
      { label: 'Modified', field: 'modified', type: 'ago' },
    ],
    columns: [
      { label: 'Entry', field: 'name' },
      { label: 'From', field: 'start_date', type: 'date' },
      { label: 'To', field: 'end_date', type: 'date' },
      { label: 'Frequency', field: 'payroll_frequency', type: 'kind' },
      { label: 'Status', field: 'status', type: 'status' },
      { label: 'Modified', field: 'modified', type: 'ago' },
    ],
    create: { doctype: 'Payroll Entry', title: 'New Payroll Entry', label: 'Payroll Entry',
      fields: [
        COMPANY,
        { fieldname: 'posting_date', label: 'Posting Date', fieldtype: 'date', default: 'today' },
        { fieldname: 'payroll_frequency', label: 'Frequency', fieldtype: 'select', selectOptions: sel(['Monthly', 'Fortnightly', 'Bimonthly', 'Weekly', 'Daily']), default: 'Monthly' },
        { fieldname: 'start_date', label: 'Start Date', fieldtype: 'date' },
        { fieldname: 'end_date', label: 'End Date', fieldtype: 'date' },
        { fieldname: 'payment_account', label: 'Payment Account', fieldtype: 'link', options: 'Account', filters: { is_group: 0 } },
        { fieldname: 'cost_center', label: 'Cost Center', fieldtype: 'link', options: 'Cost Center', filters: { is_group: 0 } },
      ] } },
  { key: 'salary-slip', section: 'Payroll', title: 'Salary Slips', doctype: 'Salary Slip', icon: FileSpreadsheet, orderBy: 'modified desc', currencyField: 'currency',
    view: [
      { label: 'Slip', field: 'name' },
      { label: 'Employee', field: 'employee_name' },
      { label: 'Period', field: 'start_date', type: 'date' },
      { label: 'To', field: 'end_date', type: 'date' },
      { label: 'Gross Pay', field: 'gross_pay', type: 'currency' },
      { label: 'Total Deduction', field: 'total_deduction', type: 'currency' },
      { label: 'Net Pay', field: 'net_pay', type: 'currency' },
      { label: 'Status', field: 'status', type: 'status' },
      { label: 'Modified', field: 'modified', type: 'ago' },
    ],
    columns: [
      { label: 'Slip', field: 'name' },
      { label: 'Employee', field: 'employee_name' },
      { label: 'Period', field: 'start_date', type: 'date' },
      { label: 'Net Pay', field: 'net_pay', type: 'currency' },
      { label: 'Status', field: 'status', type: 'status' },
      { label: 'Modified', field: 'modified', type: 'ago' },
    ] },
  { key: 'salary-structure', section: 'Payroll', title: 'Salary Structures', doctype: 'Salary Structure', icon: Layers3, orderBy: 'modified desc', currencyField: 'currency',
    view: [
      { label: 'Structure', field: 'name' },
      { label: 'Company', field: 'company' },
      { label: 'Frequency', field: 'payroll_frequency', type: 'kind' },
      { label: 'Currency', field: 'currency' },
      { label: 'Active', field: 'is_active', type: 'kind' },
      { label: 'Modified', field: 'modified', type: 'ago' },
    ],
    columns: [
      { label: 'Structure', field: 'name' },
      { label: 'Company', field: 'company' },
      { label: 'Frequency', field: 'payroll_frequency', type: 'kind' },
      { label: 'Active', field: 'is_active', type: 'kind' },
      { label: 'Modified', field: 'modified', type: 'ago' },
    ] },
  { key: 'salary-structure-assignment', section: 'Payroll', title: 'Structure Assignments', doctype: 'Salary Structure Assignment', icon: ClipboardCheck, orderBy: 'modified desc', currencyField: 'currency',
    view: [
      { label: 'Assignment', field: 'name' },
      { label: 'Employee', field: 'employee_name' },
      { label: 'Structure', field: 'salary_structure' },
      { label: 'From Date', field: 'from_date', type: 'date' },
      { label: 'Base', field: 'base', type: 'currency' },
      { label: 'Variable', field: 'variable', type: 'currency' },
      { label: 'Modified', field: 'modified', type: 'ago' },
    ],
    columns: [
      { label: 'Assignment', field: 'name' },
      { label: 'Employee', field: 'employee_name' },
      { label: 'Structure', field: 'salary_structure' },
      { label: 'From', field: 'from_date', type: 'date' },
      { label: 'Base', field: 'base', type: 'currency' },
      { label: 'Modified', field: 'modified', type: 'ago' },
    ] },
  { key: 'employee', section: 'Masters', title: 'Employees', doctype: 'Employee', icon: IdCard, orderBy: 'modified desc', currencyField: '',
    view: [
      { label: 'ID', field: 'name' },
      { label: 'Name', field: 'employee_name' },
      { label: 'Designation', field: 'designation' },
      { label: 'Department', field: 'department' },
      { label: 'Branch', field: 'branch' },
      { label: 'Company', field: 'company' },
      { label: 'Mobile', field: 'cell_number' },
      { label: 'Email', field: 'personal_email' },
      { label: 'Joined', field: 'date_of_joining', type: 'date' },
      { label: 'Status', field: 'status', type: 'status' },
    ],
    columns: [
      { label: 'ID', field: 'name' },
      { label: 'Name', field: 'employee_name' },
      { label: 'Designation', field: 'designation' },
      { label: 'Status', field: 'status', type: 'status' },
      { label: 'Modified', field: 'modified', type: 'ago' },
    ],
    create: { doctype: 'Employee', title: 'New Employee', label: 'Employee',
      fields: [
        { section: 'Employee', fieldname: 'first_name', label: 'First Name', fieldtype: 'data' },
        { section: 'Employee', fieldname: 'last_name', label: 'Last Name', fieldtype: 'data' },
        { section: 'Employee', fieldname: 'gender', label: 'Gender', fieldtype: 'link', options: 'Gender' },
        { section: 'Employee', fieldname: 'date_of_birth', label: 'Date of Birth', fieldtype: 'date' },
        { section: 'Employee', fieldname: 'date_of_joining', label: 'Date of Joining', fieldtype: 'date', default: 'today' },
        { section: 'Employment', fieldname: 'designation', label: 'Designation', fieldtype: 'link', options: 'Designation' },
        { section: 'Employment', fieldname: 'department', label: 'Department', fieldtype: 'link', options: 'Department' },
        { section: 'Employment', fieldname: 'branch', label: 'Branch', fieldtype: 'link', options: 'Branch' },
        { section: 'Employment', fieldname: 'employment_type', label: 'Employment Type', fieldtype: 'link', options: 'Employment Type' },
        COMPANY,
        { section: 'Contact', fieldname: 'cell_number', label: 'Mobile', fieldtype: 'data' },
        { section: 'Contact', fieldname: 'personal_email', label: 'Email', fieldtype: 'data' },
      ] } },
  { key: 'sales-person', section: 'Masters', title: 'Sales People', doctype: 'Sales Person', icon: UserCheck, orderBy: 'modified desc', currencyField: '',
    view: [
      { label: 'Sales Person', field: 'name' },
      { label: 'Employee', field: 'employee' },
      { label: 'Parent', field: 'parent_sales_person' },
      { label: 'Commission Rate', field: 'commission_rate' },
      { label: 'Group', field: 'is_group', type: 'kind' },
      { label: 'Enabled', field: 'enabled', type: 'kind' },
    ],
    columns: [
      { label: 'Sales Person', field: 'name' },
      { label: 'Employee', field: 'employee' },
      { label: 'Commission Rate', field: 'commission_rate' },
      { label: 'Modified', field: 'modified', type: 'ago' },
    ],
    create: { doctype: 'Sales Person', title: 'New Sales Person', label: 'Sales Person',
      fields: [
        { fieldname: 'sales_person_name', label: 'Sales Person Name', fieldtype: 'data' },
        { fieldname: 'parent_sales_person', label: 'Reports To', fieldtype: 'link', options: 'Sales Person', filters: { is_group: 1 } },
        { fieldname: 'employee', label: 'Employee', fieldtype: 'link', options: 'Employee' },
        { fieldname: 'commission_rate', label: 'Commission Rate (%)', fieldtype: 'float' },
      ] } },
  { key: 'vehicle', section: 'Masters', title: 'Vehicles', doctype: 'Vehicle', icon: Car, orderBy: 'modified desc', currencyField: '',
    view: [
      { label: 'License Plate', field: 'name' },
      { label: 'Trailer Plate', field: 'custom_trailer_plate' },
      { label: 'Transporter', field: 'custom_transporter', type: 'kind' },
      { label: 'Driver', field: 'custom_driver' },
      { label: 'Driver Name', field: 'custom_driver_name' },
      { label: 'Driver ID', field: 'custom_driver_id' },
      { label: 'Driver Contact', field: 'custom_driver_contact' },
      { label: 'Default Warehouse', field: 'custom_default_warehouse' },
      { label: 'Model', field: 'model' },
      { label: 'Make', field: 'make' },
      { label: 'Company', field: 'company' },
    ],
    columns: [
      { label: 'License Plate', field: 'name' },
      { label: 'Trailer', field: 'custom_trailer_plate' },
      { label: 'Driver', field: 'custom_driver' },
      { label: 'Transporter', field: 'custom_transporter', type: 'kind' },
      { label: 'Model', field: 'model' },
      { label: 'Modified', field: 'modified', type: 'ago' },
    ],
    create: { doctype: 'Vehicle', title: 'New Vehicle', label: 'Vehicle',
      // Compartments travel with the vehicle onto every transport document.
      child: { fieldname: 'custom_vehicle_compartments', title: 'Compartments',
        columns: [
          { fieldname: 'name1', label: 'Compartment', fieldtype: 'data', flex: 2 },
          { fieldname: 'qty', label: 'Capacity', fieldtype: 'float', flex: 1 },
        ] },
      fields: [
        { fieldname: 'license_plate', label: 'License Plate', fieldtype: 'data' },
        { fieldname: 'custom_trailer_plate', label: 'Trailer Plate', fieldtype: 'data' },
        // Transporters are suppliers, so the field picks one rather than being typed out.
        { fieldname: 'custom_transporter', label: 'Transporter', fieldtype: 'link', options: 'Supplier' },
        { fieldname: 'custom_driver', label: 'Driver', fieldtype: 'data' },
        { fieldname: 'custom_driver_name', label: 'Driver Name', fieldtype: 'data' },
        { fieldname: 'custom_driver_id', label: 'Driver ID', fieldtype: 'data' },
        { fieldname: 'custom_driver_contact', label: 'Driver Contact', fieldtype: 'data' },
        { fieldname: 'custom_default_warehouse', label: 'Default Warehouse', fieldtype: 'link', options: 'Warehouse', filters: { is_group: 0 } },
        { fieldname: 'model', label: 'Model', fieldtype: 'data' },
        { fieldname: 'make', label: 'Make', fieldtype: 'data' },
        COMPANY,
      ] } },
  { key: 'supplier', section: 'Masters', title: 'Suppliers', doctype: 'Supplier', icon: Factory, orderBy: 'modified desc', currencyField: 'default_currency',
    reportTabs: [
      { label: 'AP', report: 'ap-summary', partyType: 'Supplier' },
      { label: 'GL', report: 'general-ledger', partyType: 'Supplier' },
    ],
    view: [
      { label: 'Supplier', field: 'name' },
      { label: 'Type', field: 'supplier_type', type: 'kind' },
      { label: 'Group', field: 'supplier_group' },
      { label: 'Currency', field: 'default_currency' },
      { label: 'Tax ID', field: 'tax_id' },
      { label: 'License No', field: 'kamil_license_number' },
      { label: 'License Expiry', field: 'kamil_license_expiry', type: 'date' },
      { label: 'Mobile', field: 'mobile_no' },
      { label: 'Email', field: 'email_id' },
      { label: 'Primary Address', field: 'primary_address' },
      { label: 'Payment Terms', field: 'payment_terms' },
      { label: 'Country', field: 'country' },
      { label: 'Transporter', field: 'is_transporter', type: 'kind' },
      { label: 'Hold Type', field: 'hold_type', type: 'kind' },
      { label: 'Disabled', field: 'disabled', type: 'kind' },
    ],
    columns: [
      { label: 'Supplier', field: 'name' },
      { label: 'Type', field: 'supplier_type', type: 'kind' },
      { label: 'Group', field: 'supplier_group' },
      { label: 'Tax ID', field: 'tax_id' },
      { label: 'Modified', field: 'modified', type: 'ago' },
    ],
    // Same shape as the customer form: identity, contact, address, KYC, buying terms.
    create: { doctype: 'Supplier', title: 'New Supplier', label: 'Supplier',
      method: 'kamil.api.create_supplier',
      fields: [
        { section: 'Supplier', fieldname: 'supplier_name', label: 'Supplier Name', fieldtype: 'data' },
        { section: 'Supplier', fieldname: 'supplier_type', label: 'Type', fieldtype: 'select', selectOptions: sel(['Company', 'Individual', 'Proprietorship', 'Partnership']), default: 'Company' },
        { section: 'Supplier', fieldname: 'supplier_group', label: 'Supplier Group', fieldtype: 'link', options: 'Supplier Group' },
        { section: 'Supplier', fieldname: 'default_currency', label: 'Currency', fieldtype: 'link', options: 'Currency' },
        { section: 'Supplier', fieldname: 'default_price_list', label: 'Price List', fieldtype: 'link', options: 'Price List' },
        { section: 'Supplier', fieldname: 'country', label: 'Country', fieldtype: 'link', options: 'Country' },
        { section: 'Contact', fieldname: 'contact_first_name', label: 'Contact First Name', fieldtype: 'data', virtual: true },
        { section: 'Contact', fieldname: 'contact_last_name', label: 'Contact Last Name', fieldtype: 'data', virtual: true },
        { section: 'Contact', fieldname: 'contact_mobile', label: 'Mobile', fieldtype: 'data', virtual: true },
        { section: 'Contact', fieldname: 'contact_email', label: 'Email', fieldtype: 'data', virtual: true },
        { section: 'Address', fieldname: 'address_line1', label: 'Address Line 1', fieldtype: 'data', virtual: true },
        { section: 'Address', fieldname: 'address_line2', label: 'Address Line 2', fieldtype: 'data', virtual: true },
        { section: 'Address', fieldname: 'address_city', label: 'City / Town', fieldtype: 'data', virtual: true },
        { section: 'Address', fieldname: 'address_country', label: 'Country', fieldtype: 'link', options: 'Country', virtual: true },
        { section: 'Statutory & KYC', fieldname: 'tax_id', label: 'Tax ID / PIN', fieldtype: 'data' },
        { section: 'Statutory & KYC', fieldname: 'kamil_license_number', label: 'License Number', fieldtype: 'data' },
        { section: 'Statutory & KYC', fieldname: 'kamil_license_expiry', label: 'License Expiry', fieldtype: 'date' },
        { section: 'KYC Documents', fieldname: 'kamil_license_file', label: 'Trading / Business License', fieldtype: 'attach' },
        { section: 'KYC Documents', fieldname: 'kamil_certificate_of_incorporation', label: 'Certificate of Incorporation', fieldtype: 'attach' },
        { section: 'KYC Documents', fieldname: 'kamil_cr12', label: 'CR12', fieldtype: 'attach' },
        { section: 'Buying', fieldname: 'payment_terms', label: 'Payment Terms', fieldtype: 'link', options: 'Payment Terms Template' },
        { section: 'Buying', fieldname: 'is_transporter', label: 'Is a transporter', fieldtype: 'check' },
        { section: 'Buying', fieldname: 'is_frozen', label: 'Frozen', fieldtype: 'check' },
      ] } },
)

export function findList(key) {
  return LISTS.find((l) => l.key === key)
}

/** The list config that renders a given DocType — used to route notifications. */
export function findListByDoctype(doctype) {
  return LISTS.find((l) => l.doctype === doctype)
}
