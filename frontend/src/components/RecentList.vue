<template>
  <div class="flex flex-col gap-2">
    <h2 class="text-sm font-semibold text-ink-gray-8">{{ title }}</h2>
    <ListView
      class="h-80 rounded-lg border border-outline-gray-1 bg-surface-white"
      :columns="cols"
      :rows="rows"
      row-key="name"
      :options="{
        selectable: false,
        showTooltip: true,
        onRowClick: open,
        emptyState: { title: 'Nothing yet', description: 'No recent documents.' },
      }"
    >
      <template #cell="{ item, row, column }">
        <Badge v-if="column.key === 'status'" :theme="theme(item)" :label="item || 'Draft'" />
        <span v-else-if="column.key === 'grand_total'" class="tabular-nums text-ink-gray-7">
          {{ money(item, row.currency) }}
        </span>
        <span v-else :class="column.key === 'name' ? 'font-medium text-ink-gray-8' : 'text-ink-gray-7'">
          {{ item }}
        </span>
      </template>
    </ListView>
  </div>
</template>

<script setup>
import { Badge, ListView } from 'frappe-ui'

const props = defineProps({
  title: String,
  slug: String,
  rows: { type: Array, default: () => [] },
})

const cols = [
  { label: 'Document', key: 'name', width: 2 },
  { label: 'Party', key: 'party', width: 2 },
  { label: 'Status', key: 'status', width: 1 },
  { label: 'Total', key: 'grand_total', width: 1, align: 'right' },
]

function open(row) {
  window.location.href = `/app/${props.slug}/${encodeURIComponent(row.name)}`
}
function money(v, c) {
  try {
    return new Intl.NumberFormat('en-KE', { style: 'currency', currency: c || 'KES', maximumFractionDigits: 0 }).format(v || 0)
  } catch {
    return v
  }
}
function theme(s) {
  return { Paid: 'green', Submitted: 'blue', Draft: 'gray', Unpaid: 'orange', Overdue: 'red' }[s] || 'gray'
}
</script>
