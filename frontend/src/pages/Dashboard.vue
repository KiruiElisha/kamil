<template>
  <div class="mx-auto max-w-6xl space-y-5">
    <!-- KPI cards (Insights style: icon chip + value + label) -->
    <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      <div v-for="k in kpis" :key="k.key" class="rounded-xl border border-outline-gray-1 bg-surface-white p-4">
        <div class="flex h-9 w-9 items-center justify-center rounded-lg" :class="CHIP[k.color]">
          <component :is="k.icon" class="h-5 w-5" />
        </div>
        <div class="mt-3 truncate text-xl font-semibold text-ink-gray-9">{{ display(k) }}</div>
        <div class="truncate text-sm text-ink-gray-5">{{ k.label }}</div>
      </div>
    </div>

    <!-- Trend (frappe-ui AxisChart) -->
    <div class="h-80 rounded-xl border border-outline-gray-1 bg-surface-white p-3">
      <AxisChart :config="chartConfig" />
    </div>

    <!-- Recent -->
    <div class="grid gap-4 lg:grid-cols-2">
      <RecentList title="Recent Sales" slug="sales-invoice" :rows="data.recent_sales || []" />
      <RecentList title="Recent Purchases" slug="purchase-invoice" :rows="data.recent_purchases || []" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { AxisChart, createResource } from 'frappe-ui'
import DollarSign from '~icons/lucide/dollar-sign'
import ShoppingCart from '~icons/lucide/shopping-cart'
import TrendingUp from '~icons/lucide/trending-up'
import ArrowDownLeft from '~icons/lucide/arrow-down-left'
import ArrowUpRight from '~icons/lucide/arrow-up-right'
import ClipboardList from '~icons/lucide/clipboard-list'
import ShoppingBag from '~icons/lucide/shopping-bag'
import Receipt from '~icons/lucide/receipt'
import RecentList from '@/components/RecentList.vue'

const hub = createResource({ url: 'kamil.api.get_hub_data', auto: true })
const data = computed(() => hub.data || {})

const CHIP = {
  green: 'bg-green-100 text-green-600',
  blue: 'bg-blue-100 text-blue-600',
  amber: 'bg-amber-100 text-amber-600',
  red: 'bg-red-100 text-red-600',
  violet: 'bg-violet-100 text-violet-600',
  orange: 'bg-orange-100 text-orange-600',
}

const KPI_DEFS = [
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

const kpis = KPI_DEFS

function display(k) {
  const v = k.money ? data.value.kpis?.[k.key] : data.value.counts?.[k.key]
  if (v === null || v === undefined) return '—'
  if (!k.money) return new Intl.NumberFormat('en-KE').format(v)
  try {
    return new Intl.NumberFormat('en-KE', { style: 'currency', currency: data.value.currency || 'KES', maximumFractionDigits: 0 }).format(v)
  } catch {
    return v
  }
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
</script>
