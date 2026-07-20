// Shared 2-step wizard engine for Kamil Energy's Quick Purchase / Quick Sales pages.
// A single config object describes whether we are buying or selling; everything
// else (rendering, item grid, transport fields, API calls) is common.
frappe.provide("kamil.wizard");

kamil.wizard.KamilFlow = class KamilFlow {
	constructor(page, config) {
		this.page = page;
		this.cfg = config;
		this.controls = {};
		this.items = [];
		this.order = null; // summary returned after step 1

		this.$body = $('<div class="kamil-wizard"></div>').appendTo(page.main);
		this.render_shell();
		this.goto_step(1);
	}

	// ---- shell / stepper -------------------------------------------------
	render_shell() {
		this.$body.html(`
			<div class="kw-steps">
				<div class="kw-step" data-step="1"><span class="kw-num">1</span><span class="kw-label">${this.cfg.step1_label}</span></div>
				<div class="kw-bar"></div>
				<div class="kw-step" data-step="2"><span class="kw-num">2</span><span class="kw-label">${this.cfg.step2_label}</span></div>
			</div>
			<div class="kw-stage"></div>
		`);
		this.$stage = this.$body.find(".kw-stage");
	}

	set_stepper(step) {
		this.$body.find(".kw-step").each((i, el) => {
			const s = parseInt(el.dataset.step, 10);
			el.classList.toggle("active", s === step);
			el.classList.toggle("done", s < step);
		});
	}

	goto_step(step) {
		this.step = step;
		this.set_stepper(step);
		this.$stage.empty();
		this.controls = {};
		if (step === 1) this.render_step1();
		else this.render_step2();
	}

	// ---- helpers ---------------------------------------------------------
	make_field(df, $wrap) {
		const control = frappe.ui.form.make_control({
			df: Object.assign({ fieldtype: "Data" }, df),
			parent: $wrap.get(0),
			render_input: true,
		});
		control.set_value(df.default || "");
		control.refresh();
		this.controls[df.fieldname] = control;
		return control;
	}

	field_group(fields) {
		const $grid = $('<div class="kw-field-grid"></div>');
		fields.forEach((df) => {
			const $cell = $(`<div class="kw-cell ${df.column_class || ""}"></div>`).appendTo($grid);
			this.make_field(df, $cell);
		});
		return $grid;
	}

	value(fieldname) {
		const c = this.controls[fieldname];
		return c ? c.get_value() : undefined;
	}

	order_meta() {
		return frappe.get_meta(this.cfg.order_doctype);
	}

	// order of transport fields; custom_vehicle drives the rest
	transport_wanted() {
		return [
			"custom_vehicle",
			"custom_license_plate",
			"custom_trailer_plate",
			"custom_transporter",
			"custom_driver",
			"custom_driver_name",
			"custom_driver_id",
			"custom_driver_contact",
		];
	}

	// build a control df from the order DocType's own docfield (so a field
	// only renders when it actually exists on this site)
	field_df(fieldname) {
		const meta = this.order_meta();
		if (!meta) return null;
		const f = meta.fields.find((x) => x.fieldname === fieldname);
		if (!f) return null;
		return { fieldname: f.fieldname, label: f.label, fieldtype: f.fieldtype, options: f.options };
	}

	// Vehicle detail fields shown under the Vehicle picker. These are always
	// rendered (populated from the selected Vehicle); we use the order
	// DocType's own docfield when it exists, otherwise a sensible default,
	// so the details are visible even before the custom fields are added.
	transport_detail_defs() {
		const defaults = {
			custom_license_plate: { label: __("License Plate"), fieldtype: "Data" },
			custom_trailer_plate: { label: __("Trailer Plate"), fieldtype: "Data" },
			custom_transporter: { label: __("Transporter"), fieldtype: "Link", options: "Supplier" },
			custom_driver: { label: __("Driver"), fieldtype: "Data" },
			custom_driver_name: { label: __("Driver Name"), fieldtype: "Data" },
			custom_driver_id: { label: __("Driver ID"), fieldtype: "Data" },
			custom_driver_contact: { label: __("Driver Contact"), fieldtype: "Data" },
		};
		return Object.keys(defaults).map(
			(fn) => this.field_df(fn) || Object.assign({ fieldname: fn }, defaults[fn])
		);
	}

	// Vehicle field -> order field. When a Vehicle is picked we pull these
	// onto the form, mirroring the standard-form client scripts.
	vehicle_field_map() {
		return {
			custom_license_plate: "license_plate",
			custom_trailer_plate: "custom_trailer_plate",
			custom_transporter: "custom_transporter",
			custom_driver: "custom_driver",
			custom_driver_name: "full_name",
			custom_driver_id: "custom_driver_id",
			custom_driver_contact: "custom_driver_contact",
		};
	}

	on_vehicle_change() {
		const vehicle = this.value("custom_vehicle");
		const map = this.vehicle_field_map();

		if (!vehicle) {
			Object.keys(map).forEach((fn) => this.controls[fn] && this.controls[fn].set_value(""));
			if (this.controls["set_warehouse"]) this.controls["set_warehouse"].set_value("");
			return;
		}

		frappe.call({ method: "frappe.client.get", args: { doctype: "Vehicle", name: vehicle } }).then((r) => {
			const v = r.message;
			if (!v) return;
			Object.keys(map).forEach((fn) => {
				if (this.controls[fn] && v[map[fn]] !== undefined) this.controls[fn].set_value(v[map[fn]] || "");
			});
			if (this.controls["set_warehouse"] && v.custom_default_warehouse) {
				this.controls["set_warehouse"].set_value(v.custom_default_warehouse);
			}
		});
	}

	// ---- step 1 : order --------------------------------------------------
	render_step1() {
		const c = this.cfg;
		const $card = $('<div class="kw-card"></div>').appendTo(this.$stage);

		$card.append(`<div class="kw-section-title">${c.party_label} details</div>`);
		$card.append(
			this.field_group([
				{ fieldname: c.party_field, label: c.party_label, fieldtype: "Link", options: c.party_doctype, reqd: 1 },
				{ fieldname: "company", label: "Company", fieldtype: "Link", options: "Company", reqd: 1, default: frappe.defaults.get_default("company") },
				{ fieldname: "transaction_date", label: "Date", fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
				{ fieldname: c.schedule_field, label: c.schedule_label, fieldtype: "Date", default: frappe.datetime.get_today() },
			])
		);

		// Vehicle & Transport: the Vehicle picker drives everything below it.
		// Selecting a vehicle fills the warehouse and the driver/plate/
		// transporter details (see on_vehicle_change).
		$card.append(`<div class="kw-section-title">${__("Vehicle & Transport")}</div>`);
		const $tgrid = $('<div class="kw-field-grid"></div>').appendTo($card);
		// Vehicle and its source warehouse sit together on the first row.
		this.make_field(
			{ fieldname: "custom_vehicle", label: __("Vehicle"), fieldtype: "Link", options: "Vehicle", onchange: () => this.on_vehicle_change() },
			$('<div class="kw-cell"></div>').appendTo($tgrid)
		);
		this.make_field(
			{ fieldname: "set_warehouse", label: c.warehouse_label, fieldtype: "Link", options: "Warehouse" },
			$('<div class="kw-cell"></div>').appendTo($tgrid)
		);
		// All related vehicle details (driver, plates, transporter, ...).
		this.transport_detail_defs().forEach((df) => {
			this.make_field(df, $('<div class="kw-cell"></div>').appendTo($tgrid));
		});

		// items
		$card.append(`<div class="kw-section-title">Items</div>`);
		this.$items = $('<div class="kw-items"></div>').appendTo($card);
		this.render_items();
		$(`<button class="btn btn-xs btn-default kw-add-item"><i class="fa fa-plus"></i> Add Item</button>`)
			.appendTo($card)
			.on("click", () => this.add_item());

		// footer - two paths: order only, or order + invoice/receipt
		const $footer = $('<div class="kw-footer"></div>').appendTo(this.$stage);
		$(`<button class="btn btn-default kw-btn">${c.order_only_cta}</button>`)
			.appendTo($footer)
			.on("click", () => this.submit_order("order"));
		$(`<button class="btn btn-primary kw-btn">${c.continue_cta} &rarr;</button>`)
			.appendTo($footer)
			.on("click", () => this.submit_order("invoice"));

		if (!this.items.length) this.add_item();
	}

	render_items() {
		this.$items.empty();
		this.$items.append(`
			<div class="kw-item-head">
				<div>Item</div><div class="num">Qty</div><div class="num">Rate</div><div class="num">Amount</div><div></div>
			</div>
		`);
		this.items.forEach((row, idx) => this.render_item_row(row, idx));
		this.update_total();
	}

	render_item_row(row, idx) {
		const $row = $('<div class="kw-item-row"></div>').appendTo(this.$items);
		const $item = $('<div class="kw-cell-item"></div>').appendTo($row);
		const $qty = $(`<div class="kw-cell-num kw-cell-qty" data-label="${__("Qty")}"></div>`).appendTo($row);
		const $rate = $(`<div class="kw-cell-num kw-cell-rate" data-label="${__("Rate")}"></div>`).appendTo($row);
		const $amt = $(`<div class="kw-cell-num kw-amount" data-label="${__("Amount")}">0.00</div>`).appendTo($row);
		const $del = $('<div class="kw-cell-del"><span class="kw-remove">&times;</span></div>').appendTo($row);

		const item_ctrl = frappe.ui.form.make_control({
			df: {
				fieldtype: "Link",
				options: "Item",
				placeholder: "Item Code",
				onchange: () => {
					row.item_code = item_ctrl.get_value();
					if (row.item_code) this.fetch_item_details(row, qty_ctrl, rate_ctrl, $amt);
				},
			},
			parent: $item.get(0),
			render_input: true,
		});
		item_ctrl.set_value(row.item_code || "");

		const qty_ctrl = frappe.ui.form.make_control({
			df: { fieldtype: "Float", placeholder: "0", onchange: () => { row.qty = qty_ctrl.get_value(); this.recalc_row(row, $amt); } },
			parent: $qty.get(0),
			render_input: true,
		});
		qty_ctrl.set_value(row.qty || 0);

		const rate_ctrl = frappe.ui.form.make_control({
			df: { fieldtype: "Currency", placeholder: "0.00", onchange: () => { row.rate = rate_ctrl.get_value(); this.recalc_row(row, $amt); } },
			parent: $rate.get(0),
			render_input: true,
		});
		rate_ctrl.set_value(row.rate || 0);

		$del.find(".kw-remove").on("click", () => {
			this.items.splice(idx, 1);
			this.render_items();
		});

		this.recalc_row(row, $amt);
	}

	fetch_item_details(row, qty_ctrl, rate_ctrl, $amt) {
		frappe.db.get_value("Item", row.item_code, ["item_name", "stock_uom"]).then((r) => {
			const d = r.message || {};
			row.item_name = d.item_name;
			row.uom = d.stock_uom;
			if (!row.qty) {
				row.qty = 1;
				qty_ctrl.set_value(1);
			}
			this.recalc_row(row, $amt);
		});
	}

	recalc_row(row, $amt) {
		row.amount = flt(row.qty) * flt(row.rate);
		$amt.text(format_currency(row.amount));
		this.update_total();
	}

	update_total() {
		const total = this.items.reduce((s, r) => s + flt(r.amount), 0);
		if (this.$items) {
			this.$items.find(".kw-total-row").remove();
			this.$items.append(`<div class="kw-total-row"><div>Total</div><div class="kw-total-val">${format_currency(total)}</div></div>`);
		}
	}

	add_item() {
		this.items.push({ item_code: "", qty: 0, rate: 0, amount: 0 });
		this.render_items();
	}

	collect_transport() {
		const out = {};
		this.transport_wanted().forEach((fn) => {
			if (!this.controls[fn]) return;
			const v = this.controls[fn].get_value();
			if (v) out[fn] = v;
		});
		return out;
	}

	validate_step1() {
		const c = this.cfg;
		if (!this.value(c.party_field)) return __("Please select a {0}.", [c.party_label]);
		if (!this.value("company")) return __("Please select a Company.");
		const valid_items = this.items.filter((r) => r.item_code && flt(r.qty) > 0);
		if (!valid_items.length) return __("Add at least one item with a quantity.");
		return null;
	}

	submit_order(mode) {
		const err = this.validate_step1();
		if (err) {
			frappe.msgprint({ title: __("Incomplete"), message: err, indicator: "orange" });
			return;
		}
		const c = this.cfg;
		const payload = {
			[c.party_field]: this.value(c.party_field),
			company: this.value("company"),
			transaction_date: this.value("transaction_date"),
			[c.schedule_field]: this.value(c.schedule_field),
			set_warehouse: this.value("set_warehouse"),
			transport: this.collect_transport(),
			items: this.items
				.filter((r) => r.item_code && flt(r.qty) > 0)
				.map((r) => ({ item_code: r.item_code, qty: r.qty, rate: r.rate, uom: r.uom, warehouse: r.warehouse })),
		};

		frappe.dom.freeze(__("Creating {0}...", [c.order_doctype]));
		frappe
			.call({ method: c.create_order_method, args: { order: payload } })
			.then((r) => {
				this.order = r.message;
				frappe.show_alert({ message: __("{0} {1} created", [c.order_doctype, this.order.name]), indicator: "green" });
				if (mode === "invoice") {
					this.goto_step(2);
				} else {
					this.render_order_done();
				}
			})
			.always(() => frappe.dom.unfreeze());
	}

	// Success screen for the "order only" path. Still offers a one-click
	// route to raise the invoice/receipt afterwards.
	render_order_done() {
		const c = this.cfg;
		const o = this.order;
		this.set_stepper(2);
		this.$stage.empty();
		const $card = $('<div class="kw-card kw-done"></div>').appendTo(this.$stage);
		$card.html(`
			<div class="kw-done-check">&#10003;</div>
			<h3>${c.order_done_title}</h3>
			<p class="text-muted">${c.order_done_sub}</p>
			<div class="kw-done-total">${o.doctype}: <b>${format_currency(o.grand_total, o.currency)}</b></div>
			<div class="kw-done-links">
				<a class="btn btn-default kw-btn" href="/app/${frappe.router.slug(c.order_doctype)}/${encodeURIComponent(o.name)}" target="_blank">${__("Open")} ${o.name}</a>
				<button class="btn btn-primary kw-btn kw-proceed">${c.proceed_cta} &rarr;</button>
			</div>
			<button class="btn btn-link btn-sm kw-restart">${c.restart_cta}</button>
		`);
		$card.find(".kw-proceed").on("click", () => this.goto_step(2));
		$card.find(".kw-restart").on("click", () => this.restart());
	}

	restart() {
		this.items = [];
		this.order = null;
		this.goto_step(1);
	}

	// ---- step 2 : invoice ------------------------------------------------
	render_step2() {
		const c = this.cfg;
		const o = this.order;
		const $card = $('<div class="kw-card"></div>').appendTo(this.$stage);

		$card.append(`
			<div class="kw-order-banner">
				<span class="kw-check">&#10003;</span>
				<div>
					<div class="kw-order-name"><a href="/app/${frappe.router.slug(c.order_doctype)}/${encodeURIComponent(o.name)}" target="_blank">${o.name}</a> submitted</div>
					<div class="kw-order-sub">${c.step2_intro}</div>
				</div>
			</div>
		`);

		// order summary table
		let rows = (o.items || [])
			.map(
				(r) => `<tr>
					<td>${frappe.utils.escape_html(r.item_name || r.item_code)}</td>
					<td class="num">${format_number(r.qty)} ${frappe.utils.escape_html(r.uom || "")}</td>
					<td class="num">${format_currency(r.rate, o.currency)}</td>
					<td class="num">${format_currency(r.amount, o.currency)}</td>
				</tr>`
			)
			.join("");
		$card.append(`
			<div class="kw-summary">
				<table class="table table-bordered">
					<thead><tr><th>Item</th><th class="num">Qty</th><th class="num">Rate</th><th class="num">Amount</th></tr></thead>
					<tbody>${rows}</tbody>
					<tfoot><tr><td colspan="3" class="num"><b>Grand Total</b></td><td class="num"><b>${format_currency(o.grand_total, o.currency)}</b></td></tr></tfoot>
				</table>
			</div>
		`);

		$card.append(`<div class="kw-section-title">${c.step2_form_title}</div>`);
		const fields = [
			{ fieldname: "posting_date", label: "Posting Date", fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
			{ fieldname: "set_warehouse", label: c.warehouse_label, fieldtype: "Link", options: "Warehouse", default: this.value_from_order_warehouse() },
		];
		fields.push(...c.step2_fields);
		$card.append(this.field_group(fields));

		const $footer = $('<div class="kw-footer"></div>').appendTo(this.$stage);
		$(`<button class="btn btn-default kw-btn">${c.skip_invoice_cta}</button>`)
			.appendTo($footer)
			.on("click", () => this.render_order_done());
		$(`<button class="btn btn-primary kw-btn">${c.step2_cta}</button>`)
			.appendTo($footer)
			.on("click", () => this.submit_invoice());
	}

	value_from_order_warehouse() {
		const o = this.order;
		if (o && o.items && o.items.length && o.items[0].warehouse) return o.items[0].warehouse;
		return "";
	}

	submit_invoice() {
		const c = this.cfg;
		if (!this.value("posting_date")) {
			frappe.msgprint({ title: __("Incomplete"), message: __("Posting Date is required."), indicator: "orange" });
			return;
		}
		const payload = { posting_date: this.value("posting_date"), set_warehouse: this.value("set_warehouse") };
		c.step2_fields.forEach((df) => {
			const v = this.value(df.fieldname);
			if (v) payload[df.fieldname] = v;
		});

		frappe.dom.freeze(__("Creating {0} & updating stock...", [c.invoice_doctype]));
		frappe
			.call({ method: c.create_invoice_method, args: Object.assign({ [c.invoice_arg]: this.order.name }, { [c.invoice_payload_key]: payload }) })
			.then((r) => {
				frappe.dom.unfreeze();
				this.render_done(r.message);
			})
			.catch(() => frappe.dom.unfreeze());
	}

	render_done(inv) {
		const c = this.cfg;
		this.set_stepper(3);
		this.$stage.empty();
		const $card = $('<div class="kw-card kw-done"></div>').appendTo(this.$stage);
		$card.html(`
			<div class="kw-done-check">&#10003;</div>
			<h3>${c.done_title}</h3>
			<p class="text-muted">${c.done_sub}</p>
			<div class="kw-done-total">${c.invoice_doctype}: <b>${format_currency(inv.grand_total, inv.currency)}</b></div>
			<div class="kw-done-links">
				<a class="btn btn-default kw-btn" href="/app/${frappe.router.slug(c.order_doctype)}/${encodeURIComponent(this.order.name)}" target="_blank">${this.order.name}</a>
				<a class="btn btn-primary kw-btn" href="/app/${frappe.router.slug(c.invoice_doctype)}/${encodeURIComponent(inv.name)}" target="_blank">${inv.name}</a>
			</div>
			<button class="btn btn-link btn-sm kw-restart">${c.restart_cta}</button>
		`);
		$card.find(".kw-restart").on("click", () => this.restart());
	}
};
