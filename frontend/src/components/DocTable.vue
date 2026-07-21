<template>
  <div class="flex h-[calc(100vh-9.5rem)] flex-col gap-3">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold text-ink-gray-8">{{ title }}</h2>
      <Button v-if="canCreate" variant="solid" :label="newLabel" @click="openNew">
        <template #prefix><Plus class="h-4 w-4" /></template>
      </Button>
    </div>

    <ListView
      class="flex-1 rounded-lg border border-outline-gray-1 bg-surface-white"
      :columns="listColumns"
      :rows="rows"
      row-key="name"
      :options="{
        selectable: false,
        showTooltip: true,
        resizeColumn: false,
        onRowClick: openDoc,
        emptyState: { title: 'No records', description: 'Nothing here yet.' },
      }"
    >
      <template #cell="{ item, row, column }">
        <Badge v-if="column.key === 'status'" :theme="statusTheme(item)" :label="item || 'Draft'" />
        <span v-else-if="column.type === 'currency'" class="tabular-nums text-ink-gray-7">
          {{ fmtCurrency(item, row[currencyField]) }}
        </span>
        <span v-else-if="column.type === 'date'" class="text-ink-gray-6">{{ fmtDate(item) }}</span>
        <span v-else :class="column.key === 'name' ? 'font-medium text-ink-gray-8' : 'text-ink-gray-7'">
          {{ item }}
        </span>
      </template>
    </ListView>

    <CreateDialog v-if="createConfig" v-model="showCreate" :config="createConfig" @created="onCreated" />
    <PaymentDialog v-if="special === 'payment'" v-model="showPayment" @created="onCreated" />
    <DocViewDialog
      v-model="showView"
      :doctype="doctype"
      :name="viewName"
      :columns="columns"
      :child="createConfig?.child || null"
      :currency-field="currencyField"
      @submitted="onCreated"
    />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Button, Badge, ListView, createListResource } from 'frappe-ui'
import Plus from '~icons/lucide/plus'
import CreateDialog from '@/components/dialogs/CreateDialog.vue'
import PaymentDialog from '@/components/dialogs/PaymentDialog.vue'
import DocViewDialog from '@/components/dialogs/DocViewDialog.vue'

const props = defineProps({
  title: { type: String, required: true },
  doctype: { type: String, required: true },
  columns: { type: Array, required: true },
  filters: { type: Object, default: () => ({}) },
  orderBy: { type: String, default: 'modified desc' },
  currencyField: { type: String, default: 'currency' },
  createConfig: { type: Object, default: null },
  special: { type: String, default: '' },
})

const showCreate = ref(false)
const showPayment = ref(false)
const showView = ref(false)
const viewName = ref('')

const canCreate = computed(() => !!props.createConfig || props.special === 'payment')
const newLabel = computed(() =>
  props.special === 'payment' ? 'New Payment' : 'New ' + (props.createConfig?.label || 'Record'),
)

function openNew() {
  if (props.special === 'payment') showPayment.value = true
  else showCreate.value = true
}
function onCreated() {
  list.reload()
}

const slug = computed(() => props.doctype.toLowerCase().replace(/ /g, '-'))

const queryFields = computed(() => {
  const set = new Set(['name'])
  let hasCurrency = false
  props.columns.forEach((c) => {
    set.add(c.field)
    if (c.type === 'currency') hasCurrency = true
  })
  if (hasCurrency && props.currencyField) set.add(props.currencyField)
  return [...set]
})

const listColumns = computed(() =>
  props.columns.map((c) => ({
    label: c.label,
    key: c.field,
    type: c.type,
    width: c.field === 'name' ? 2 : 1,
    align: c.type === 'currency' ? 'right' : 'left',
  })),
)

const list = createListResource({
  doctype: props.doctype,
  fields: queryFields.value,
  filters: props.filters,
  orderBy: props.orderBy,
  pageLength: 100,
  auto: true,
})

const rows = computed(() => list.data || [])

function openDoc(row) {
  viewName.value = row.name
  showView.value = true
}
function fmtCurrency(v, currency) {
  if (v === null || v === undefined) return ''
  try {
    return new Intl.NumberFormat('en-KE', { style: 'currency', currency: currency || 'KES', maximumFractionDigits: 0 }).format(v)
  } catch {
    return v
  }
}
function fmtDate(v) {
  if (!v) return ''
  return new Date(v).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}
function statusTheme(status) {
  const map = {
    Paid: 'green', Completed: 'green', Submitted: 'blue', Draft: 'gray',
    Unpaid: 'orange', Overdue: 'red', Cancelled: 'red', Return: 'gray',
    'Partly Paid': 'orange', 'To Bill': 'orange', 'To Deliver': 'orange',
    'To Receive': 'orange', 'On Hold': 'red',
  }
  return map[status] || 'gray'
}
</script>
