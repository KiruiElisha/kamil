<template>
  <div class="flex flex-col gap-2">
    <div class="flex items-center gap-2">
      <span
        v-if="icon"
        class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg"
        :class="color === 'green' ? 'bg-green-100 text-green-600' : 'bg-blue-100 text-blue-600'"
      >
        <component :is="icon" class="h-4 w-4" />
      </span>
      <h2 class="truncate text-sm font-semibold text-ink-gray-8">{{ title }}</h2>
    </div>

    <!-- Mobile: stacked cards (no horizontal scrolling) -->
    <div v-if="isMobile" class="max-h-80 overflow-y-auto rounded-lg border border-outline-gray-1 bg-surface-white">
      <div v-if="!rows.length" class="p-6 text-center text-sm text-ink-gray-5">No recent documents.</div>
      <button
        v-for="row in rows"
        :key="row.name"
        class="flex w-full items-start justify-between gap-3 border-b border-outline-gray-1 px-3 py-2.5 text-left last:border-0 active:bg-surface-gray-2"
        @click="open(row)"
      >
        <div class="min-w-0 flex-1">
          <div class="truncate text-sm font-medium text-ink-gray-8">{{ row.name }}</div>
          <div v-if="row.party" class="mt-0.5 truncate text-xs text-ink-gray-5">{{ row.party }}</div>
        </div>
        <div class="flex shrink-0 flex-col items-end gap-1">
          <span class="text-sm tabular-nums text-ink-gray-8">{{ money(row.grand_total, row.currency) }}</span>
          <Badge :theme="theme(row.status)" :label="row.status || 'Draft'" />
        </div>
      </button>
    </div>

    <!-- Desktop: table -->
    <ListView
      v-else
      class="kamil-list h-80 rounded-lg border border-outline-gray-1 bg-surface-white"
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

    <DocViewDialog
      v-model="showView"
      :doctype="doctype"
      :name="viewName"
      :columns="cfg?.columns || []"
      :child="cfg?.create?.child || null"
      :currency-field="cfg?.currencyField ?? 'currency'"
    />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Badge, ListView } from 'frappe-ui'
import { useIsMobile } from '@/composables/useIsMobile'
import { haptic } from '@/utils/haptics'
import { findList } from '@/data/doctypes.js'
import DocViewDialog from '@/components/dialogs/DocViewDialog.vue'
import { defaultCurrency } from '@/utils/money.js'

const props = defineProps({
  title: String,
  slug: String,
  rows: { type: Array, default: () => [] },
  // Optional header icon, styled like the dashboard cards' chip.
  icon: { type: [Object, Function], default: null },
  color: { type: String, default: 'blue' },
})

const isMobile = useIsMobile()

// `slug` matches the list key in doctypes.js (e.g. 'sales-invoice')
const cfg = computed(() => findList(props.slug))
const doctype = computed(
  () =>
    cfg.value?.doctype ||
    props.slug.split('-').map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join(' '),
)
const showView = ref(false)
const viewName = ref('')

const cols = [
  { label: 'Document', key: 'name', width: 2 },
  { label: 'Party', key: 'party', width: 2 },
  { label: 'Status', key: 'status', width: 1 },
  { label: 'Total', key: 'grand_total', width: 1, align: 'right' },
]

function open(row) {
  haptic()
  viewName.value = row.name
  showView.value = true
}
function money(v, c) {
  try {
    return new Intl.NumberFormat('en-KE', { style: 'currency', currency: c || defaultCurrency(), maximumFractionDigits: 0 }).format(v || 0)
  } catch {
    return v
  }
}
function theme(s) {
  return { Paid: 'green', Submitted: 'blue', Draft: 'gray', Unpaid: 'orange', Overdue: 'red' }[s] || 'gray'
}
</script>
