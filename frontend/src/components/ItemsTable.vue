<template>
  <div class="space-y-2">
    <div class="text-xs font-medium text-ink-gray-5">{{ title || 'Items' }}</div>
    <div
      v-for="(row, i) in rows"
      :key="i"
      class="flex flex-col gap-2 rounded-md border border-outline-gray-1 p-2 md:flex-row md:items-end"
    >
      <div
        v-for="col in columns"
        :key="col.fieldname"
        class="w-full min-w-0 md:w-auto md:min-w-[7.5rem]"
        :style="{ flex: col.flex || 1 }"
      >
        <label class="mb-0.5 hidden text-[10px] leading-none text-ink-gray-5 md:block">{{ col.label }}</label>
        <LinkField
          v-if="col.fieldtype === 'link'"
          :doctype="col.options"
          :filters="col.filters || {}"
          :placeholder="col.label"
          :modelValue="row[col.fieldname] || ''"
          @update:modelValue="(v) => set(i, col.fieldname, v)"
        />
        <ComboField
          v-else-if="col.fieldtype === 'select'"
          :options="col.selectOptions"
          :placeholder="col.label"
          :modelValue="row[col.fieldname]"
          @update:modelValue="(v) => set(i, col.fieldname, v)"
        />
        <!-- Amount is qty x rate: derived, never typed, so it cannot disagree
             with the figures beside it or with what the server recalculates. -->
        <div v-else-if="col.fieldtype === 'amount'">
          <div class="truncate py-1.5 text-sm font-medium tabular-nums text-ink-gray-8">
            {{ money(amountOf(row)) }}
          </div>
        </div>
        <FormControl
          v-else
          :type="col.fieldtype === 'float' || col.fieldtype === 'currency' ? 'number' : 'text'"
          :placeholder="col.label"
          :modelValue="row[col.fieldname]"
          @update:modelValue="(v) => set(i, col.fieldname, v)"
        />
      </div>
      <Button variant="ghost" @click="remove(i)">
        <template #icon><Trash class="h-4 w-4 text-ink-gray-6" /></template>
      </Button>
    </div>

    <div class="flex items-center justify-between gap-3 px-1">
      <Button variant="subtle" label="Add row" @click="add">
        <template #prefix><Plus class="h-4 w-4" /></template>
      </Button>
      <div v-if="hasAmount" class="text-sm">
        <span class="text-ink-gray-5">Total</span>
        <span class="ml-2 font-semibold tabular-nums text-ink-gray-9">{{ money(total) }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { Button, FormControl, call } from 'frappe-ui'
import LinkField from '@/components/LinkField.vue'
import ComboField from '@/components/ComboField.vue'
import Plus from '~icons/lucide/plus'
import Trash from '~icons/lucide/trash-2'

const props = defineProps({
  title: String,
  columns: { type: Array, required: true },
  modelValue: { type: Array, default: () => [] },
  // context used to look up the right price for a picked item
  doctype: { type: String, default: '' },
  party: { type: String, default: '' },
  company: { type: String, default: '' },
  // The document's own warehouse, used when the item has no default of its own.
  warehouse: { type: String, default: '' },
  currency: { type: String, default: '' },
})

const rateCol = computed(() => props.columns.find((c) => c.fieldtype === 'currency'))
const qtyCol = computed(() => props.columns.find((c) => c.fieldname === 'qty'))
const hasAmount = computed(() => props.columns.some((c) => c.fieldtype === 'amount'))

function amountOf(row) {
  const qty = Number(row[qtyCol.value?.fieldname || 'qty']) || 0
  const rate = Number(row[rateCol.value?.fieldname || 'rate']) || 0
  return qty * rate
}
const total = computed(() => rows.value.reduce((sum, r) => sum + amountOf(r), 0))

function money(v) {
  try {
    return props.currency
      ? new Intl.NumberFormat('en-KE', { style: 'currency', currency: props.currency, maximumFractionDigits: 2 }).format(v || 0)
      : new Intl.NumberFormat('en-KE', { maximumFractionDigits: 2 }).format(v || 0)
  } catch {
    return v
  }
}

async function fetchRate(i, itemCode) {
  if (!props.doctype || !itemCode) return
  try {
    const r = await call('kamil.api.get_item_rate', {
      item_code: itemCode,
      doctype: props.doctype,
      party: props.party || null,
      company: props.company || null,
    })
    const row = rows.value[i]
    // the user may have changed the row while we were fetching
    if (!row || row.item_code !== itemCode) return
    if (rateCol.value && !row[rateCol.value.fieldname]) row[rateCol.value.fieldname] = r?.rate || 0
    if (!row.qty) row.qty = 1
    // The item's own defaults fill the line in — a warehouse the user has already
    // chosen for this row is left alone.
    if (r?.uom && !row.uom) row.uom = r.uom
    if (r?.warehouse && !row.warehouse) row.warehouse = r.warehouse
    else if (!row.warehouse && props.warehouse) row.warehouse = props.warehouse
    sync()
  } catch (e) {
    /* leave the rate for manual entry */
  }
}
const emit = defineEmits(['update:modelValue'])

const rows = ref(props.modelValue.length ? [...props.modelValue] : [{}])

function sync() {
  emit('update:modelValue', rows.value)
}
function set(i, field, val) {
  rows.value[i][field] = val
  sync()
  if (field === 'item_code' && val) fetchRate(i, val)
}
function add() {
  rows.value.push({})
  sync()
}
function remove(i) {
  rows.value.splice(i, 1)
  if (!rows.value.length) rows.value.push({})
  sync()
}
watch(rows, sync, { deep: true })

// The rows are seeded once at mount, but a form can be filled in *after* that — a
// mapped document ("Create Sales Invoice" off an order) arrives once the dialog is
// already on screen. Without this the table kept its blank starter row and then
// emitted it straight back, wiping the lines that had just been mapped in.
watch(
  () => props.modelValue,
  (incoming) => {
    if (!Array.isArray(incoming)) return
    // Ignore the echo of our own emit, which would restart the cycle.
    if (JSON.stringify(incoming) === JSON.stringify(rows.value)) return
    rows.value = incoming.length ? incoming.map((row) => ({ ...row })) : [{}]
  },
  { deep: true },
)
</script>
