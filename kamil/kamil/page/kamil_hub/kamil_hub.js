frappe.pages["kamil-hub"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Kamil Energy"),
		single_column: true,
	});

	frappe.require(["/assets/kamil/css/kamil_hub.css"], () => new KamilHub(page));
};

const KH_ICONS = {
	cart: '<circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>',
	tag: '<path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/>',
	clipboard:
		'<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>',
	file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
	users: '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
	box: '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>',
	truck: '<rect x="1" y="3" width="15" height="13"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/>',
	archive:
		'<polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5"/><line x1="10" y1="12" x2="14" y2="12"/>',
	card: '<rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/>',
	chart: '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>',
	up: '<line x1="7" y1="17" x2="17" y2="7"/><polyline points="7 7 17 7 17 17"/>',
	down: '<line x1="17" y1="7" x2="7" y2="17"/><polyline points="17 17 7 17 7 7"/>',
	plus: '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
};

function kh_icon(name) {
	return `<svg class="kh-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${KH_ICONS[name] || ""}</svg>`;
}

const KH_STATUS_COLOR = {
	Paid: "green",
	Completed: "green",
	Submitted: "blue",
	Unpaid: "orange",
	"Partly Paid": "orange",
	"Unpaid and Discounted": "orange",
	Overdue: "red",
	"Overdue and Discounted": "red",
	Draft: "gray",
	Cancelled: "gray",
	Return: "gray",
	"Credit Note Issued": "gray",
	"Debit Note Issued": "gray",
	"On Hold": "red",
};

class KamilHub {
	constructor(page) {
		this.page = page;
		this.$body = $('<div class="kamil-hub"></div>').appendTo(page.main);
		this.loading = false;
		this.current_company = null;

		this.company_field = page.add_field({
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			change: () => {
				// Only reload on a genuine change. Setting the field's value
				// after a load fires this handler too (Link controls fire
				// asynchronously); comparing against the loaded company breaks
				// the reload loop that made the page flicker.
				const v = this.company_field.get_value() || null;
				if (v !== this.current_company) this.load(v);
			},
		});

		this.load();
	}

	load(company) {
		if (this.loading) return;
		this.loading = true;
		this.render_skeleton();
		frappe
			.call({ method: "kamil.api.get_hub_data", args: { company: company || "" } })
			.then((r) => {
				this.loading = false;
				this.data = r.message || {};
				this.current_company = this.data.company || null;
				// Reflect the resolved company without re-triggering a load.
				if ((this.company_field.get_value() || null) !== this.current_company) {
					this.company_field.set_value(this.data.company || "");
				}
				this.render();
			})
			.catch(() => {
				this.loading = false;
				this.$body.html(`<div class="kh-empty">${__("Could not load dashboard data.")}</div>`);
			});
	}

	render_skeleton() {
		this.$body.html(`
			<div class="kh-skeleton">
				<div class="kh-sk kh-sk-hero"></div>
				<div class="kh-sk-row">${'<div class="kh-sk kh-sk-tile"></div>'.repeat(4)}</div>
				<div class="kh-sk kh-sk-block"></div>
			</div>
		`);
	}

	fmt(value) {
		return format_currency(value || 0, this.data.currency);
	}

	render() {
		const d = this.data;
		this.$body.empty();
		this.render_hero();
		this.render_kpis(d.kpis || {});
		this.render_trend(d.monthly || []);
		this.render_shortcuts(d.counts || {});
		this.render_recent(d);
	}

	// ---- hero --------------------------------------------------------------
	render_hero() {
		const today = moment().format("dddd, D MMMM YYYY");
		this.$body.append(`
			<div class="kh-hero">
				<div>
					<div class="kh-hero-title">${__("Kamil Energy")}</div>
					<div class="kh-hero-sub">${frappe.utils.escape_html(today)}${
						this.data.company ? " · " + frappe.utils.escape_html(this.data.company) : ""
					}</div>
				</div>
				<div class="kh-hero-actions">
					<a class="kh-action kh-action-purchase" href="/app/quick-purchase">
						${kh_icon("plus")}<span>${__("New Purchase")}</span>
					</a>
					<a class="kh-action kh-action-sale" href="/app/quick-sales">
						${kh_icon("plus")}<span>${__("New Sale")}</span>
					</a>
				</div>
			</div>
		`);
	}

	// ---- KPI tiles ----------------------------------------------------------
	render_kpis(k) {
		const tiles = [
			{ key: "mtd_purchases", label: __("Purchases this month"), icon: "cart", cls: "purchase" },
			{ key: "mtd_sales", label: __("Sales this month"), icon: "tag", cls: "sale" },
			{ key: "payables", label: __("To pay suppliers"), icon: "up", cls: "muted" },
			{ key: "receivables", label: __("To collect"), icon: "down", cls: "muted" },
		].filter((t) => k[t.key] !== null && k[t.key] !== undefined);
		if (!tiles.length) return;

		const html = tiles
			.map(
				(t) => `
				<div class="kh-tile">
					<div class="kh-tile-top">
						<span class="kh-chip kh-chip-${t.cls}">${kh_icon(t.icon)}</span>
						<span class="kh-tile-label">${t.label}</span>
					</div>
					<div class="kh-tile-value">${this.fmt(k[t.key])}</div>
				</div>`
			)
			.join("");
		this.$body.append(`<div class="kh-kpis">${html}</div>`);
	}

	// ---- trend chart ---------------------------------------------------------
	render_trend(monthly) {
		const has_data = monthly.some((m) => m.purchases || m.sales);
		const $panel = $(`
			<div class="kh-panel kh-trend">
				<div class="kh-panel-head">
					<h4>${__("Purchases vs Sales")}</h4>
					<div class="kh-legend">
						<span><i class="kh-dot kh-dot-purchase"></i>${__("Purchases")}</span>
						<span><i class="kh-dot kh-dot-sale"></i>${__("Sales")}</span>
					</div>
				</div>
				<div class="kh-chart"></div>
				<details class="kh-data">
					<summary>${__("View data")}</summary>
					<table class="table table-sm">
						<thead><tr><th>${__("Month")}</th><th class="num">${__("Purchases")}</th><th class="num">${__("Sales")}</th></tr></thead>
						<tbody>
							${monthly
								.map(
									(m) => `<tr>
										<td>${frappe.utils.escape_html(m.label)}</td>
										<td class="num">${this.fmt(m.purchases)}</td>
										<td class="num">${this.fmt(m.sales)}</td>
									</tr>`
								)
								.join("")}
						</tbody>
					</table>
				</details>
			</div>
		`).appendTo(this.$body);

		const $chart = $panel.find(".kh-chart");
		if (!has_data) {
			$chart.html(`<div class="kh-empty">${__("No submitted invoices in the last 6 months.")}</div>`);
			$panel.find(".kh-data").hide();
			return;
		}

		const style = getComputedStyle(this.$body.get(0));
		const colors = [
			(style.getPropertyValue("--kh-purchase") || "#2a78d6").trim(),
			(style.getPropertyValue("--kh-sale") || "#008300").trim(),
		];
		new frappe.Chart($chart.get(0), {
			data: {
				labels: monthly.map((m) => m.label),
				datasets: [
					{ name: __("Purchases"), values: monthly.map((m) => m.purchases) },
					{ name: __("Sales"), values: monthly.map((m) => m.sales) },
				],
			},
			type: "bar",
			height: 240,
			colors: colors,
			barOptions: { spaceRatio: 0.55 },
			axisOptions: { xAxisMode: "tick", shortenYAxisNumbers: 1 },
			tooltipOptions: { formatTooltipY: (v) => this.fmt(v) },
		});
	}

	// ---- shortcuts -----------------------------------------------------------
	render_shortcuts(c) {
		const groups = [
			{
				title: __("Buying"),
				items: [
					{ label: __("New Purchase"), sub: __("2-step purchase & receive"), href: "/app/quick-purchase", icon: "cart", primary: "purchase" },
					{ label: __("New Purchase Order"), sub: __("Standard order"), href: "/app/purchase-order/new", icon: "plus" },
					{ label: __("New Purchase Invoice"), sub: __("Standard invoice"), href: "/app/purchase-invoice/new", icon: "plus" },
					{ label: __("Purchase Orders"), href: "/app/purchase-order", icon: "clipboard", count: c.open_po, badge: __("open") },
					{ label: __("Purchase Invoices"), href: "/app/purchase-invoice", icon: "file", count: c.unpaid_pinv, badge: __("unpaid") },
					{ label: __("Suppliers"), href: "/app/supplier", icon: "users", count: c.supplier },
					{ label: __("Accounts Payable"), href: "/app/query-report/Accounts%20Payable", icon: "chart" },
				],
			},
			{
				title: __("Selling"),
				items: [
					{ label: __("New Sale"), sub: __("2-step sell & deliver"), href: "/app/quick-sales", icon: "tag", primary: "sale" },
					{ label: __("New Sales Order"), sub: __("Standard order"), href: "/app/sales-order/new", icon: "plus" },
					{ label: __("New Sales Invoice"), sub: __("Standard invoice"), href: "/app/sales-invoice/new", icon: "plus" },
					{ label: __("Sales Orders"), href: "/app/sales-order", icon: "clipboard", count: c.open_so, badge: __("open") },
					{ label: __("Sales Invoices"), href: "/app/sales-invoice", icon: "file", count: c.unpaid_sinv, badge: __("unpaid") },
					{ label: __("Customers"), href: "/app/customer", icon: "users", count: c.customer },
					{ label: __("Accounts Receivable"), href: "/app/query-report/Accounts%20Receivable", icon: "chart" },
				],
			},
			{
				title: __("Stock & More"),
				items: [
					{ label: __("Items"), href: "/app/item", icon: "box", count: c.item },
					{ label: __("Vehicles"), href: "/app/vehicle", icon: "truck", count: c.vehicle },
					{ label: __("Warehouses"), href: "/app/warehouse", icon: "archive", count: c.warehouse },
					{ label: __("Payment Entries"), href: "/app/payment-entry", icon: "card", count: c.payment_entry },
					{ label: __("Stock Ledger"), href: "/app/query-report/Stock%20Ledger", icon: "chart" },
				],
			},
		];

		groups.forEach((g) => {
			const cards = g.items
				.map((it) => {
					const badge =
						it.count !== null && it.count !== undefined
							? `<span class="kh-count">${format_number(it.count, null, 0)}${it.badge ? ` <em>${it.badge}</em>` : ""}</span>`
							: "";
					return `
						<a class="kh-card ${it.primary ? `kh-card-primary kh-card-${it.primary}` : ""}" href="${it.href}">
							<span class="kh-card-icon">${kh_icon(it.icon)}</span>
							<span class="kh-card-body">
								<span class="kh-card-label">${it.label}</span>
								${it.sub ? `<span class="kh-card-sub">${it.sub}</span>` : ""}
							</span>
							${badge}
						</a>`;
				})
				.join("");
			this.$body.append(`
				<div class="kh-group">
					<div class="kh-group-title">${g.title}</div>
					<div class="kh-cards">${cards}</div>
				</div>
			`);
		});
	}

	// ---- recent documents ----------------------------------------------------
	render_recent(d) {
		const $row = $('<div class="kh-recent-row"></div>').appendTo(this.$body);
		this.recent_panel($row, __("Recent Purchases"), "purchase-invoice", d.recent_purchases || []);
		this.recent_panel($row, __("Recent Sales"), "sales-invoice", d.recent_sales || []);
	}

	recent_panel($row, title, slug, rows) {
		const list = rows.length
			? rows
					.map((r) => {
						const color = KH_STATUS_COLOR[r.status] || "gray";
						return `
							<a class="kh-doc" href="/app/${slug}/${encodeURIComponent(r.name)}">
								<span class="kh-doc-main">
									<span class="kh-doc-name">${frappe.utils.escape_html(r.name)}</span>
									<span class="kh-doc-sub">${frappe.utils.escape_html(r.party || "")} · ${
										r.posting_date ? frappe.datetime.str_to_user(r.posting_date) : ""
									}</span>
								</span>
								<span class="kh-doc-side">
									<span class="kh-doc-amount">${format_currency(r.grand_total || 0, r.currency)}</span>
									<span class="indicator-pill ${color}">${__(r.status || "Draft")}</span>
								</span>
							</a>`;
					})
					.join("")
			: `<div class="kh-empty">${__("Nothing here yet.")}</div>`;

		$row.append(`
			<div class="kh-panel">
				<div class="kh-panel-head">
					<h4>${title}</h4>
					<a class="kh-see-all" href="/app/${slug}">${__("See all")}</a>
				</div>
				<div class="kh-docs">${list}</div>
			</div>
		`);
	}
}
