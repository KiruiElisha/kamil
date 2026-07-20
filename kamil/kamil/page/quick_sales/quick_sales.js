frappe.pages["quick-sales"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Quick Sales"),
		single_column: true,
	});
	page.set_indicator(__("Sell & Deliver"), "green");

	frappe.require(
		["/assets/kamil/js/kamil_wizard.js", "/assets/kamil/css/kamil_wizard.css"],
		() => {
			frappe.model.with_doctype("Sales Order", () => {
				new kamil.wizard.KamilFlow(page, {
					order_doctype: "Sales Order",
					invoice_doctype: "Sales Invoice",

					party_field: "customer",
					party_label: "Customer",
					party_doctype: "Customer",

					schedule_field: "delivery_date",
					schedule_label: "Delivery Date",
					warehouse_label: "Source Warehouse",

					step1_label: __("Sales Order"),
					step2_label: __("Deliver & Invoice"),

					// step 1 actions
					order_only_cta: __("Submit Order Only"),
					continue_cta: __("Submit & Deliver"),

					create_order_method: "kamil.api.create_sales_order",
					create_invoice_method: "kamil.api.create_sales_invoice",
					invoice_arg: "sales_order",
					invoice_payload_key: "delivery",

					// order-only success screen
					order_done_title: __("Sales Order submitted"),
					order_done_sub: __("The order is confirmed. Deliver the goods and raise the invoice now, or later."),
					proceed_cta: __("Deliver & Invoice Now"),

					step2_intro: __("Confirm delivery and raise the customer invoice."),
					step2_form_title: __("Delivery & Invoice"),
					step2_fields: [
						{ fieldname: "po_no", label: __("Customer's PO No"), fieldtype: "Data" },
					],
					skip_invoice_cta: __("Finish without Invoice"),
					step2_cta: __("Deliver & Create Invoice"),

					done_title: __("Sale completed"),
					done_sub: __("Stock has been delivered and the customer invoice is raised."),
					restart_cta: __("New Sale"),
				});
			});
		}
	);
};
