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

export const SECTIONS = ['Selling', 'Buying', 'Inventory', 'Accounts', 'Masters']

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
const SALES_ITEMS = { fieldname: 'items', title: 'Items', columns: [ITEM_COL, QTY_COL, RATE_COL, AMOUNT_COL] }
const BUY_ITEMS = SALES_ITEMS

export const LISTS = [
  // Selling — invoices carry the stock movement themselves (update_stock).
  { key: 'sales-order', section: 'Selling', title: 'Sales Orders', doctype: 'Sales Order', icon: ShoppingCart, orderBy: 'modified desc',
    columns: [ { label: 'Order', field: 'name' }, { label: 'Customer', field: 'customer_name' }, { label: 'Date', field: 'transaction_date', type: 'date' }, { label: 'Status', field: 'status', type: 'status' }, { label: 'Total', field: 'grand_total', type: 'currency' }, { label: 'Modified', field: 'modified', type: 'date' } ],
    create: { doctype: 'Sales Order', title: 'New Sales Order', label: 'Order', child: SALES_ITEMS,
      fields: [ COMPANY, CUSTOMER, { fieldname: 'delivery_date', label: 'Delivery Date', fieldtype: 'date', default: 'today' }, VEHICLE, WAREHOUSE ] } },
  { key: 'sales-invoice', section: 'Selling', title: 'Sales Invoices', doctype: 'Sales Invoice', icon: Receipt, orderBy: 'modified desc',
    columns: [ { label: 'Invoice', field: 'name' }, { label: 'Customer', field: 'customer_name' }, { label: 'Date', field: 'posting_date', type: 'date' }, { label: 'Status', field: 'status', type: 'status' }, { label: 'Total', field: 'grand_total', type: 'currency' }, { label: 'Modified', field: 'modified', type: 'date' } ],
    create: { doctype: 'Sales Invoice', title: 'New Sales Invoice', label: 'Invoice', child: SALES_ITEMS,
      fields: [ COMPANY, CUSTOMER, { fieldname: 'due_date', label: 'Due Date', fieldtype: 'date' }, VEHICLE, WAREHOUSE, { fieldname: 'update_stock', label: 'Update stock', fieldtype: 'check', default: 1 } ] } },
  // Buying
  { key: 'material-request', section: 'Buying', title: 'Material Requests', doctype: 'Material Request', icon: ClipboardList, orderBy: 'modified desc',
    columns: [ { label: 'Request', field: 'name' }, { label: 'Type', field: 'material_request_type', type: 'kind' }, { label: 'Date', field: 'transaction_date', type: 'date' }, { label: 'Status', field: 'status', type: 'status' }, { label: 'Modified', field: 'modified', type: 'date' } ],
    create: { doctype: 'Material Request', title: 'New Material Request', label: 'Request',
      child: { fieldname: 'items', title: 'Items', columns: [ ITEM_COL, QTY_COL, wh('warehouse', 'For Warehouse'), { fieldname: 'schedule_date', label: 'Required By', fieldtype: 'date', flex: 1 } ] },
      fields: [ COMPANY, { fieldname: 'material_request_type', label: 'Type', fieldtype: 'select', selectOptions: sel(['Purchase', 'Material Transfer', 'Material Issue', 'Manufacture', 'Customer Provided']), default: 'Purchase' }, { fieldname: 'schedule_date', label: 'Required By', fieldtype: 'date', default: 'today' } ] } },
  { key: 'purchase-order', section: 'Buying', title: 'Purchase Orders', doctype: 'Purchase Order', icon: ShoppingBag, orderBy: 'modified desc',
    columns: [ { label: 'Order', field: 'name' }, { label: 'Supplier', field: 'supplier_name' }, { label: 'Date', field: 'transaction_date', type: 'date' }, { label: 'Status', field: 'status', type: 'status' }, { label: 'Total', field: 'grand_total', type: 'currency' }, { label: 'Modified', field: 'modified', type: 'date' } ],
    create: { doctype: 'Purchase Order', title: 'New Purchase Order', label: 'Order', child: BUY_ITEMS,
      fields: [ COMPANY, SUPPLIER, { fieldname: 'schedule_date', label: 'Required By', fieldtype: 'date', default: 'today' }, WAREHOUSE ] } },
  { key: 'purchase-invoice', section: 'Buying', title: 'Purchase Invoices', doctype: 'Purchase Invoice', icon: FileText, orderBy: 'modified desc',
    columns: [ { label: 'Invoice', field: 'name' }, { label: 'Supplier', field: 'supplier_name' }, { label: 'Date', field: 'posting_date', type: 'date' }, { label: 'Status', field: 'status', type: 'status' }, { label: 'Total', field: 'grand_total', type: 'currency' }, { label: 'Modified', field: 'modified', type: 'date' } ],
    create: { doctype: 'Purchase Invoice', title: 'New Purchase Invoice', label: 'Invoice', child: BUY_ITEMS,
      fields: [ COMPANY, SUPPLIER, WAREHOUSE, { fieldname: 'update_stock', label: 'Update stock', fieldtype: 'check', default: 1 } ] } },
  // Inventory
  { key: 'item', section: 'Inventory', title: 'Items', doctype: 'Item', icon: Package, orderBy: 'modified desc',
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
    columns: [ { label: 'Item Code', field: 'name' }, { label: 'Name', field: 'item_name' }, { label: 'Group', field: 'item_group' }, { label: 'UOM', field: 'stock_uom' }, { label: 'Modified', field: 'modified', type: 'date' } ],
    create: { doctype: 'Item', title: 'New Item', label: 'Item',
      fields: [ { fieldname: 'item_code', label: 'Item Code', fieldtype: 'data' }, { fieldname: 'item_name', label: 'Item Name', fieldtype: 'data' }, { fieldname: 'item_group', label: 'Item Group', fieldtype: 'link', options: 'Item Group' }, { fieldname: 'stock_uom', label: 'Default UOM', fieldtype: 'link', options: 'UOM' } ] } },
  { key: 'stock-entry', section: 'Inventory', title: 'Stock Entries', doctype: 'Stock Entry', icon: Repeat, orderBy: 'modified desc',
    columns: [ { label: 'Entry', field: 'name' }, { label: 'Type', field: 'stock_entry_type', type: 'kind' }, { label: 'Date', field: 'posting_date', type: 'date' }, { label: 'State', field: 'docstatus', type: 'docstatus' }, { label: 'Modified', field: 'modified', type: 'date' } ],
    create: { doctype: 'Stock Entry', title: 'New Stock Entry', label: 'Entry',
      child: { fieldname: 'items', title: 'Items', columns: [ ITEM_COL, QTY_COL, wh('s_warehouse', 'Source'), wh('t_warehouse', 'Target') ] },
      fields: [ COMPANY, { fieldname: 'stock_entry_type', label: 'Type', fieldtype: 'select', selectOptions: sel(['Material Issue', 'Material Receipt', 'Material Transfer', 'Repack']), default: 'Material Receipt' } ] } },
  { key: 'stock-reconciliation', section: 'Inventory', title: 'Stock Reconciliations', doctype: 'Stock Reconciliation', icon: Scale, orderBy: 'modified desc',
    columns: [ { label: 'Reconciliation', field: 'name' }, { label: 'Purpose', field: 'purpose', type: 'kind' }, { label: 'Date', field: 'posting_date', type: 'date' }, { label: 'State', field: 'docstatus', type: 'docstatus' }, { label: 'Modified', field: 'modified', type: 'date' } ],
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
      { label: 'Modified', field: 'modified', type: 'date' },
    ] },
  { key: 'payment-entry', section: 'Accounts', title: 'Payment Entries', doctype: 'Payment Entry', icon: CreditCard, orderBy: 'modified desc', currencyField: 'paid_to_account_currency', special: 'payment',
    columns: [ { label: 'Payment', field: 'name' }, { label: 'Type', field: 'payment_type', type: 'kind' }, { label: 'Party', field: 'party_name' }, { label: 'Date', field: 'posting_date', type: 'date' }, { label: 'State', field: 'docstatus', type: 'docstatus' }, { label: 'Amount', field: 'paid_amount', type: 'currency' }, { label: 'Modified', field: 'modified', type: 'date' } ] },
  { key: 'journal-entry', section: 'Accounts', title: 'Journal Entries', doctype: 'Journal Entry', icon: BookOpen, orderBy: 'modified desc', currencyField: '',
    columns: [ { label: 'Entry', field: 'name' }, { label: 'Type', field: 'voucher_type', type: 'kind' }, { label: 'Date', field: 'posting_date', type: 'date' }, { label: 'State', field: 'docstatus', type: 'docstatus' }, { label: 'Debit', field: 'total_debit', type: 'currency' }, { label: 'Modified', field: 'modified', type: 'date' } ],
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
    view: [
      { label: 'Customer', field: 'name' },
      { label: 'Type', field: 'customer_type', type: 'kind' },
      { label: 'Group', field: 'customer_group' },
      { label: 'Territory', field: 'territory' },
      { label: 'Currency', field: 'default_currency' },
      { label: 'Price List', field: 'default_price_list' },
      { label: 'Tax ID', field: 'tax_id' },
      { label: 'KRA PIN', field: 'kamil_kra_pin' },
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
      { label: 'Modified', field: 'modified', type: 'date' },
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
        { section: 'Statutory & KYC', fieldname: 'kamil_kra_pin', label: 'KRA PIN', fieldtype: 'data' },
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
      { label: 'Driver', field: 'custom_driver_name' },
      { label: 'Transporter', field: 'custom_transporter', type: 'kind' },
      { label: 'Model', field: 'model' },
      { label: 'Modified', field: 'modified', type: 'date' },
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
      { label: 'Modified', field: 'modified', type: 'date' },
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
