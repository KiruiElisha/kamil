<template>
  <div class="mx-auto w-full min-h-0 max-w-6xl flex-1 space-y-4 overflow-auto p-3 md:p-5">
    <Tabs class="!flex-none" v-model="tab" :tabs="tabs" />

    <!-- ---------------- Overview ---------------- -->
    <template v-if="tab === 0">
      <template v-if="loading">
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <Skeleton v-for="n in 10" :key="n" class="h-[86px]" />
        </div>
        <Skeleton class="h-80 w-full" />
        <div class="grid gap-4 lg:grid-cols-2"><Skeleton class="h-80" /><Skeleton class="h-80" /></div>
      </template>
      <template v-else>
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <StatCard
            v-for="k in kpis"
            :key="k.key"
            :label="k.label"
            :value="display(k)"
            :icon="k.icon"
            :color="k.color"
          />
        </div>

        <div class="h-80 rounded-xl border border-outline-gray-1 bg-surface-white p-3">
          <AxisChart :config="chartConfig" />
        </div>

        <div class="grid gap-4 lg:grid-cols-2">
          <RecentList title="Recent Sales" slug="sales-invoice" :rows="data.recent_sales || []" :icon="Receipt" color="green" />
          <RecentList title="Recent Purchases" slug="purchase-invoice" :rows="data.recent_purchases || []" :icon="ShoppingBag" color="blue" />
        </div>
      </template>
    </template>

    <!-- ---------------- Sales / Purchases ---------------- -->
    <template v-else-if="tab === 1 || tab === 2">
      <template v-if="ana.loading">
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-4"><Skeleton v-for="n in 4" :key="n" class="h-[86px]" /></div>
        <Skeleton class="h-72 w-full" />
        <div class="grid gap-4 lg:grid-cols-2"><Skeleton class="h-64" /><Skeleton class="h-64" /></div>
      </template>
      <template v-else-if="ana.data">
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <StatCard
            :label="tab === 1 ? 'Sales (12 mo)' : 'Purchases (12 mo)'"
            :value="fmtMoney(ana.data.total_12m, ana.data.currency)"
            :icon="TrendingUp"
            :color="tab === 1 ? 'green' : 'blue'"
          />
          <StatCard
            :label="tab === 1 ? 'Invoices' : 'Bills'"
            :value="fmtNum(ana.data.count_12m)"
            :icon="Receipt"
            :color="tab === 1 ? 'green' : 'blue'"
          />
          <StatCard label="Average value" :value="fmtMoney(ana.data.avg_value, ana.data.currency)" :icon="Scale" color="violet" />
          <StatCard label="Largest" :value="fmtMoney(ana.data.largest, ana.data.currency)" :icon="Crown" color="amber" />
          <StatCard
            :label="tab === 1 ? 'Customers' : 'Suppliers'"
            :value="fmtNum(ana.data.unique_parties)"
            :icon="Users"
            color="blue"
          />
          <StatCard
            :label="tab === 1 ? 'Top customer' : 'Top supplier'"
            :value="ana.data.top_parties?.[0]?.label || '—'"
            :icon="Award"
            color="orange"
            small
          />
        </div>

        <div class="h-72 rounded-xl border border-outline-gray-1 bg-surface-white p-3">
          <AxisChart :config="anaChart" />
        </div>

        <div class="grid gap-4 lg:grid-cols-2">
          <div class="h-72 rounded-xl border border-outline-gray-1 bg-surface-white p-3">
            <DonutChart :config="anaDonut" />
          </div>
          <RankList
            :title="tab === 1 ? 'Top Customers' : 'Top Suppliers'"
            :icon="Users"
            :color="tab === 1 ? 'green' : 'blue'"
            :rows="ana.data.top_parties || []"
            :currency="ana.data.currency"
            :bar-class="tab === 1 ? 'bg-green-500' : 'bg-blue-500'"
            :party-type="tab === 1 ? 'Customer' : 'Supplier'"
          />
        </div>
        <RankList
          title="Top Items"
          :icon="Package"
          color="violet"
          :rows="ana.data.top_items || []"
          :currency="ana.data.currency"
          :bar-class="tab === 1 ? 'bg-emerald-500' : 'bg-indigo-500'"
        />
      </template>
    </template>

    <!-- ---------------- Receivables & Payables ---------------- -->
    <template v-else-if="tab === 3">
      <template v-if="arap.loading">
        <div class="grid grid-cols-2 gap-3"><Skeleton class="h-[86px]" /><Skeleton class="h-[86px]" /></div>
        <div class="grid gap-4 lg:grid-cols-2"><Skeleton class="h-64" /><Skeleton class="h-64" /></div>
      </template>
      <template v-else-if="arap.data">
        <div class="grid grid-cols-2 gap-3">
          <StatCard label="Total receivable" :value="fmtMoney(arap.data.receivable.total, arap.data.currency)" :icon="ArrowDownLeft" color="amber" />
          <StatCard label="Total payable" :value="fmtMoney(arap.data.payable.total, arap.data.currency)" :icon="ArrowUpRight" color="red" />
        </div>
        <div class="grid gap-4 lg:grid-cols-2">
          <div class="h-72 rounded-xl border border-outline-gray-1 bg-surface-white p-3">
            <DonutChart :config="donut(arap.data.receivable.buckets, 'Receivables ageing')" />
          </div>
          <div class="h-72 rounded-xl border border-outline-gray-1 bg-surface-white p-3">
            <DonutChart :config="donut(arap.data.payable.buckets, 'Payables ageing')" />
          </div>
        </div>
        <div class="grid gap-4 lg:grid-cols-2">
          <RankList title="Receivables ageing" :icon="ArrowDownLeft" color="amber" :rows="arap.data.receivable.buckets" :currency="arap.data.currency" bar-class="bg-amber-500" />
          <RankList title="Payables ageing" :icon="ArrowUpRight" color="red" :rows="arap.data.payable.buckets" :currency="arap.data.currency" bar-class="bg-red-500" />
          <RankList title="Top outstanding customers" :icon="Users" color="amber" :rows="arap.data.receivable.top" :currency="arap.data.currency" bar-class="bg-amber-500" party-type="Customer" />
          <RankList title="Top outstanding suppliers" :icon="Users" color="red" :rows="arap.data.payable.top" :currency="arap.data.currency" bar-class="bg-red-500" party-type="Supplier" />
        </div>
      </template>
    </template>

    <!-- ---------------- Inventory ---------------- -->
    <template v-else-if="tab === 4">
      <template v-if="inventory.loading">
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-5"><Skeleton v-for="n in 5" :key="n" class="h-[86px]" /></div>
        <div class="grid gap-4 lg:grid-cols-2"><Skeleton class="h-72" /><Skeleton class="h-72" /></div>
      </template>
      <template v-else-if="inventory.data">
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <StatCard label="Stock value" :value="fmtMoney(inventory.data.total_value, inventory.data.currency)" :icon="Wallet" color="violet" />
          <StatCard label="Active SKUs" :value="fmtNum(inventory.data.active_skus)" :icon="Package" color="blue" />
          <StatCard label="Items in stock" :value="fmtNum(inventory.data.stocked_skus)" :icon="PackageCheck" color="green" />
          <StatCard label="Out of stock" :value="fmtNum(inventory.data.out_of_stock)" :icon="PackageX" color="red" />
          <StatCard label="Low stock" :value="fmtNum(inventory.data.low_stock)" :icon="TriangleAlert" color="amber" />
        </div>
        <div class="grid gap-4 lg:grid-cols-2">
          <div class="h-72 rounded-xl border border-outline-gray-1 bg-surface-white p-3">
            <DonutChart :config="donut(inventory.data.by_group, 'Stock value by item group')" />
          </div>
          <RankList
            title="Top items by stock value"
            :icon="Package"
            color="violet"
            :rows="inventory.data.top_items || []"
            :currency="inventory.data.currency"
            bar-class="bg-violet-500"
          />
        </div>
        <RankList
          title="Stock value by item group"
          :icon="Layers"
          color="blue"
          :rows="inventory.data.by_group || []"
          :currency="inventory.data.currency"
          bar-class="bg-blue-500"
        />
      </template>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { AxisChart, DonutChart, Tabs, createResource, call } from 'frappe-ui'
import DollarSign from '~icons/lucide/dollar-sign'
import ShoppingCart from '~icons/lucide/shopping-cart'
import TrendingUp from '~icons/lucide/trending-up'
import ArrowDownLeft from '~icons/lucide/arrow-down-left'
import ArrowUpRight from '~icons/lucide/arrow-up-right'
import ClipboardList from '~icons/lucide/clipboard-list'
import ShoppingBag from '~icons/lucide/shopping-bag'
import Receipt from '~icons/lucide/receipt'
import LayoutDashboard from '~icons/lucide/layout-dashboard'
import Wallet from '~icons/lucide/wallet'
import Package from '~icons/lucide/package'
import PackageCheck from '~icons/lucide/package-check'
import PackageX from '~icons/lucide/package-x'
import TriangleAlert from '~icons/lucide/triangle-alert'
import Scale from '~icons/lucide/scale'
import Crown from '~icons/lucide/crown'
import Award from '~icons/lucide/award'
import Users from '~icons/lucide/users'
import Layers from '~icons/lucide/layers'
import RecentList from '@/components/RecentList.vue'
import RankList from '@/components/RankList.vue'
import StatCard from '@/components/StatCard.vue'
import Skeleton from '@/components/Skeleton.vue'
import { defaultCurrency } from '@/utils/money.js'

const tab = ref(0)
const tabs = [
  { label: 'Overview', icon: LayoutDashboard },
  { label: 'Sales', icon: TrendingUp },
  { label: 'Purchases', icon: ShoppingBag },
  { label: 'Receivables & Payables', icon: Wallet },
  { label: 'Inventory', icon: Package },
]

// ---- Overview data
const hub = createResource({ url: 'kamil.api.get_hub_data', auto: true })
const data = computed(() => hub.data || {})
const loading = computed(() => hub.loading && !hub.data)

// ---- Lazy analytics per tab
const sales = ref({ loading: false, data: null })
const purchases = ref({ loading: false, data: null })
const arap = ref({ loading: false, data: null })
const inventory = ref({ loading: false, data: null })
const ana = computed(() => (tab.value === 1 ? sales.value : purchases.value))

async function load(store, method) {
  if (store.value.data || store.value.loading) return
  store.value.loading = true
  try {
    store.value.data = await call(method)
  } catch (e) {
    store.value.data = null
  } finally {
    store.value.loading = false
  }
}

watch(
  tab,
  (t) => {
    if (t === 1) load(sales, 'kamil.api.get_sales_analytics')
    else if (t === 2) load(purchases, 'kamil.api.get_purchase_analytics')
    else if (t === 3) load(arap, 'kamil.api.get_ar_ap_analytics')
    else if (t === 4) load(inventory, 'kamil.api.get_inventory_analytics')
  },
  { immediate: true },
)

// Card styling (the chip palette) now lives in StatCard, so every card matches.
const kpis = [
  { key: 'today_sales', label: 'Sales today', money: true, color: 'green', icon: DollarSign },
  { key: 'mtd_sales', label: 'Sales this month', money: true, color: 'green', icon: ShoppingCart },
  { key: 'ytd_sales', label: 'Sales YTD', money: true, color: 'green', icon: TrendingUp },
  { key: 'receivables', label: 'To collect', money: true, color: 'amber', icon: ArrowDownLeft },
  { key: 'open_so', label: 'Open Sales Orders', color: 'blue', icon: ClipboardList },
  { key: 'today_purchases', label: 'Purchases today', money: true, color: 'blue', icon: DollarSign },
  { key: 'mtd_purchases', label: 'Purchases this month', money: true, color: 'blue', icon: ShoppingBag },
  { key: 'payables', label: 'To pay suppliers', money: true, color: 'red', icon: ArrowUpRight },
  { key: 'open_po', label: 'Open Purchase Orders', color: 'violet', icon: ClipboardList },
  { key: 'unpaid_sinv', label: 'Unpaid Sales Invoices', color: 'orange', icon: Receipt },
]

function display(k) {
  const v = k.money ? data.value.kpis?.[k.key] : data.value.counts?.[k.key]
  if (v === null || v === undefined) return '—'
  return k.money ? fmtMoney(v, data.value.currency) : fmtNum(v)
}

const chartConfig = computed(() => ({
  data: data.value.monthly || [],
  title: 'Purchases vs Sales',
  subtitle: 'Last 6 months',
  xAxis: { key: 'label', type: 'category' },
  yAxis: { title: '' },
  series: [
    { name: 'sales', type: 'bar', color: '#16a34a' },
    { name: 'purchases', type: 'bar', color: '#2563eb' },
  ],
}))

const anaChart = computed(() => ({
  data: ana.value.data?.monthly || [],
  title: tab.value === 1 ? 'Monthly Sales' : 'Monthly Purchases',
  subtitle: 'Last 12 months',
  xAxis: { key: 'label', type: 'category' },
  yAxis: { title: '' },
  series: [{ name: 'total', type: 'bar', color: tab.value === 1 ? '#16a34a' : '#2563eb' }],
}))

const anaDonut = computed(() => ({
  data: ana.value.data?.top_items || [],
  title: tab.value === 1 ? 'Revenue share by item' : 'Spend share by item',
  categoryColumn: 'label',
  valueColumn: 'value',
  maxSliceCount: 8,
}))

function donut(rows, title) {
  return {
    data: (rows || []).filter((r) => r.value),
    title,
    categoryColumn: 'label',
    valueColumn: 'value',
    maxSliceCount: 8,
  }
}

function fmtMoney(v, c) {
  try {
    return new Intl.NumberFormat('en-KE', { style: 'currency', currency: c || defaultCurrency(), maximumFractionDigits: 0 }).format(v || 0)
  } catch {
    return v
  }
}
function fmtNum(v) {
  return new Intl.NumberFormat('en-KE').format(v || 0)
}
</script>
