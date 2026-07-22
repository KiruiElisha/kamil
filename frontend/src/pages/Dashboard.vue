<template>
  <div class="mx-auto w-full min-h-0 max-w-6xl flex-1 space-y-4 overflow-auto p-3 md:p-5">
    <Tabs v-model="tab" :tabs="tabs" />

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
          <div v-for="k in kpis" :key="k.key" class="rounded-xl border border-outline-gray-1 bg-surface-white p-4">
            <div class="flex h-9 w-9 items-center justify-center rounded-lg" :class="CHIP[k.color]">
              <component :is="k.icon" class="h-5 w-5" />
            </div>
            <div class="mt-3 truncate text-xl font-semibold text-ink-gray-9">{{ display(k) }}</div>
            <div class="truncate text-sm text-ink-gray-5">{{ k.label }}</div>
          </div>
        </div>

        <div class="h-80 rounded-xl border border-outline-gray-1 bg-surface-white p-3">
          <AxisChart :config="chartConfig" />
        </div>

        <div class="grid gap-4 lg:grid-cols-2">
          <RecentList title="Recent Sales" slug="sales-invoice" :rows="data.recent_sales || []" />
          <RecentList title="Recent Purchases" slug="purchase-invoice" :rows="data.recent_purchases || []" />
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
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat :label="tab === 1 ? 'Sales (12 mo)' : 'Purchases (12 mo)'" :value="fmtMoney(ana.data.total_12m, ana.data.currency)" />
          <Stat :label="tab === 1 ? 'Invoices' : 'Bills'" :value="fmtNum(ana.data.count_12m)" />
          <Stat label="Average value" :value="fmtMoney(ana.data.avg_value, ana.data.currency)" />
          <Stat :label="tab === 1 ? 'Top customer' : 'Top supplier'" :value="ana.data.top_parties?.[0]?.label || '—'" small />
        </div>

        <div class="h-72 rounded-xl border border-outline-gray-1 bg-surface-white p-3">
          <AxisChart :config="anaChart" />
        </div>

        <div class="grid gap-4 lg:grid-cols-2">
          <RankList
            :title="tab === 1 ? 'Top Customers' : 'Top Suppliers'"
            :rows="ana.data.top_parties || []"
            :currency="ana.data.currency"
            :bar-class="tab === 1 ? 'bg-green-500' : 'bg-blue-500'"
            :party-type="tab === 1 ? 'Customer' : 'Supplier'"
          />
          <RankList
            title="Top Items"
            :rows="ana.data.top_items || []"
            :currency="ana.data.currency"
            :bar-class="tab === 1 ? 'bg-emerald-500' : 'bg-indigo-500'"
          />
        </div>
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
          <Stat label="Total receivable" :value="fmtMoney(arap.data.receivable.total, arap.data.currency)" />
          <Stat label="Total payable" :value="fmtMoney(arap.data.payable.total, arap.data.currency)" />
        </div>
        <div class="grid gap-4 lg:grid-cols-2">
          <RankList title="Receivables ageing" :rows="arap.data.receivable.buckets" :currency="arap.data.currency" bar-class="bg-amber-500" />
          <RankList title="Payables ageing" :rows="arap.data.payable.buckets" :currency="arap.data.currency" bar-class="bg-red-500" />
          <RankList title="Top outstanding customers" :rows="arap.data.receivable.top" :currency="arap.data.currency" bar-class="bg-amber-500" party-type="Customer" />
          <RankList title="Top outstanding suppliers" :rows="arap.data.payable.top" :currency="arap.data.currency" bar-class="bg-red-500" party-type="Supplier" />
        </div>
      </template>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch, h } from 'vue'
import { AxisChart, Tabs, createResource, call } from 'frappe-ui'
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
import RecentList from '@/components/RecentList.vue'
import RankList from '@/components/RankList.vue'
import Skeleton from '@/components/Skeleton.vue'

const tab = ref(0)
const tabs = [
  { label: 'Overview', icon: LayoutDashboard },
  { label: 'Sales', icon: TrendingUp },
  { label: 'Purchases', icon: ShoppingBag },
  { label: 'Receivables & Payables', icon: Wallet },
]

// Small inline stat card
const Stat = (props) =>
  h('div', { class: 'rounded-xl border border-outline-gray-1 bg-surface-white p-4' }, [
    h('div', { class: 'truncate text-xs text-ink-gray-5' }, props.label),
    h(
      'div',
      { class: ['mt-1.5 truncate font-semibold text-ink-gray-9', props.small ? 'text-base' : 'text-xl'] },
      props.value,
    ),
  ])
Stat.props = ['label', 'value', 'small']

// ---- Overview data
const hub = createResource({ url: 'kamil.api.get_hub_data', auto: true })
const data = computed(() => hub.data || {})
const loading = computed(() => hub.loading && !hub.data)

// ---- Lazy analytics per tab
const sales = ref({ loading: false, data: null })
const purchases = ref({ loading: false, data: null })
const arap = ref({ loading: false, data: null })
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
  },
  { immediate: true },
)

const CHIP = {
  green: 'bg-green-100 text-green-600',
  blue: 'bg-blue-100 text-blue-600',
  amber: 'bg-amber-100 text-amber-600',
  red: 'bg-red-100 text-red-600',
  violet: 'bg-violet-100 text-violet-600',
  orange: 'bg-orange-100 text-orange-600',
}

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

function fmtMoney(v, c) {
  try {
    return new Intl.NumberFormat('en-KE', { style: 'currency', currency: c || 'KES', maximumFractionDigits: 0 }).format(v || 0)
  } catch {
    return v
  }
}
function fmtNum(v) {
  return new Intl.NumberFormat('en-KE').format(v || 0)
}
</script>
