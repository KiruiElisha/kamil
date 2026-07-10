frappe.pages["quick-purchase"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Quick Purchase"),
		single_column: true,
	});
	page.set_indicator(__("Purchase & Receive"), "blue");

	frappe.require(
		["/assets/kamil/js/kamil_wizard.js", "/assets/kamil/css/kamil_wizard.css"],
		() => {
			// Ensure the DocType metas are loaded so transport/compartment
			// custom fields (if present) can be rendered.
			frappe.model.with_doctype("Purchase Order", () => {
				new kamil.wizard.KamilFlow(page, {
					order_doctype: "Purchase Order",
					invoice_doctype: "Purchase Invoice",

					party_field: "supplier",
					party_label: "Supplier",
					party_doctype: "Supplier",

					schedule_field: "schedule_date",
					schedule_label: "Required By",
					warehouse_label: "Accepted Warehouse",

					step1_label: __("Purchase Order"),
					step2_label: __("Receive & Invoice"),
					step1_cta: __("Create Purchase Order"),

					create_order_method: "kamil.api.create_purchase_order",
					create_invoice_method: "kamil.api.create_purchase_invoice",
					invoice_arg: "purchase_order",
					invoice_payload_key: "receipt",

					step2_intro: __("Record the goods received and the supplier's invoice."),
					step2_form_title: __("Receipt & Supplier Invoice"),
					step2_fields: [
						{ fieldname: "bill_no", label: __("Supplier Invoice No"), fieldtype: "Data" },
						{ fieldname: "bill_date", label: __("Supplier Invoice Date"), fieldtype: "Date" },
						{ fieldname: "custom_supplier_invoice", label: __("Supplier Invoice Copy"), fieldtype: "Attach", column_class: "full" },
					],
					step2_cta: __("Receive & Create Invoice"),

					done_title: __("Purchase completed"),
					done_sub: __("Stock has been received and the supplier invoice is booked."),
					restart_cta: __("New Purchase"),
				});
			});
		}
	);
};
