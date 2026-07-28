<template>
  <div v-if="loading" class="space-y-2">
    <Skeleton v-for="n in 12" :key="n" class="h-8 w-full" />
  </div>
  <div
    v-else-if="error"
    class="whitespace-pre-line rounded-lg border border-red-200 bg-red-50 p-6 text-center text-sm text-red-700"
  >
    {{ error }}
  </div>
  <div
    v-else
    class="kamil-report min-h-0 flex-1 overflow-auto rounded-lg border border-outline-gray-1 bg-surface-white"
  >
    <table class="w-full text-sm">
      <thead class="sticky top-0 z-10">
        <tr class="bg-surface-gray-3">
          <th
            v-for="c in columns"
            :key="c.fieldname"
            class="whitespace-nowrap border-b border-outline-gray-2 px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-gray-6"
            :class="isNumeric(c) ? 'text-right' : 'text-left'"
          >
            {{ c.label }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(r, i) in rows"
          :key="i"
          class="border-b border-outline-gray-1 transition-colors last:border-0 hover:bg-blue-50"
          :class="rowClass(r, i)"
        >
          <td
            v-for="(c, ci) in columns"
            :key="c.fieldname"
            class="whitespace-nowrap px-3 py-1.5"
            :class="cellClass(r, c)"
            :style="ci === 0 && indentOf(r) ? { paddingLeft: 12 + indentOf(r) * 14 + 'px' } : null"
          >
            <Badge
              v-if="isStatus(c) && r[c.fieldname]"
              :theme="statusTheme(r[c.fieldname])"
              :label="String(r[c.fieldname])"
            />
            <button
              v-else-if="drillFor(c, r)"
              class="text-blue-600 underline decoration-blue-300 underline-offset-2 hover:text-blue-700"
              @click.stop="$emit('drill', drillFor(c, r))"
            >
              {{ format(r[c.fieldname], c) }}
            </button>
            <span v-else>{{ format(r[c.fieldname], c) }}</span>
          </td>
        </tr>

        <tr v-if="!rows.length">
          <td :colspan="Math.max(columns.length, 1)" class="p-8 text-center text-sm text-ink-gray-5">
            {{ emptyText }}
          </td>
        </tr>
      </tbody>

      <!-- Column totals, where the caller computed them -->
      <tfoot v-if="rows.length && hasTotals" class="sticky bottom-0">
        <tr class="border-t-2 border-outline-gray-3 bg-surface-gray-3 font-semibold text-ink-gray-9">
          <td
            v-for="(c, ci) in columns"
            :key="c.fieldname"
            class="whitespace-nowrap px-3 py-2"
            :class="isNumeric(c) ? 'text-right tabular-nums' : ''"
          >
            <span v-if="ci === 0 && totals[c.fieldname] === undefined">Total</span>
            <span v-else-if="totals[c.fieldname] !== undefined">{{ format(totals[c.fieldname], c) }}</span>
          </td>
        </tr>
      </tfoot>
    </table>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Badge } from 'frappe-ui'
import Skeleton from '@/components/Skeleton.vue'
import { statusTheme } from '@/utils/status.js'
import { formatValue, isNumeric, isTotalRow, isGroupRow, linkTarget } from '@/utils/reportFormat.js'

const props = defineProps({
  columns: { type: Array, default: () => [] },
  rows: { type: Array, default: () => [] },
  currency: { type: String, default: 'KES' },
  totals: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  emptyText: { type: String, default: 'No data for this period.' },
})
defineEmits(['drill'])

const hasTotals = computed(() => Object.keys(props.totals || {}).length > 0)

function format(v, c) {
  return formatValue(v, c, props.currency)
}

function isStatus(c) {
  return c.fieldname === 'status' || c.fieldname === 'workflow_state' || /_status$/.test(c.fieldname)
}

function indentOf(row) {
  const indent = Number(row?.indent)
  return Number.isFinite(indent) && indent > 0 ? indent : 0
}

/** Where a cell leads when clicked — parties and accounts open their ledger. */
function drillFor(column, row) {
  const target = linkTarget(column, row)
  const value = row?.[column.fieldname]
  if (!target || !value) return null
  return { target, value: String(value), fieldname: column.fieldname, row }
}

// Rows alternate, group headers and totals stand out, so a long statement stays readable.
function rowClass(row, index) {
  if (isTotalRow(row)) return 'bg-amber-50 font-semibold text-ink-gray-9'
  if (isGroupRow(row) && indentOf(row) === 0) return 'bg-surface-gray-2 font-medium text-ink-gray-8'
  return index % 2 ? 'bg-surface-gray-1' : 'bg-surface-white'
}

function cellClass(row, column) {
  const classes = []
  if (isNumeric(column)) {
    classes.push('text-right tabular-nums')
    const value = Number(row[column.fieldname])
    if (Number.isFinite(value) && value < 0) classes.push('text-red-600')
    else if (Number.isFinite(value) && value > 0 && column.fieldtype === 'Currency')
      classes.push('text-ink-gray-8')
    else classes.push('text-ink-gray-7')
  } else if (column.fieldtype === 'Date' || column.fieldtype === 'Datetime') {
    classes.push('text-ink-gray-6')
  } else {
    classes.push('text-ink-gray-7')
  }
  return classes
}
</script>
