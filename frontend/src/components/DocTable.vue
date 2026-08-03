<template>
  <div ref="rootEl" class="flex min-h-0 flex-1 flex-col gap-3">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold text-ink-gray-8">{{ title }}</h2>
      <Button v-if="canCreate" variant="solid" :label="newLabel" @click="openNew">
        <template #prefix><Plus class="h-4 w-4" /></template>
      </Button>
    </div>

    <!-- Per-doctype KPI strip -->
    <div v-if="kpis.length" class="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <StatCard
        v-for="k in kpis"
        :key="k.label"
        :label="k.label"
        :value="kpiValue(k)"
        :icon="k.icon"
        :color="k.color"
      />
    </div>

    <!-- Search + filters -->
    <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
      <TextInput
        class="w-full sm:max-w-xs"
        type="text"
        :modelValue="search"
        :placeholder="'Search ' + title.toLowerCase() + '…'"
        @update:modelValue="onSearchInput"
      />
      <ComboField
        v-if="statusOptions.length"
        class="w-full sm:w-56"
        :options="statusOptions"
        :modelValue="comboStatus"
        placeholder="All statuses"
        @update:modelValue="onStatus"
      />
      <Badge v-if="statusList.length > 1" theme="orange" :label="statusList.join(' or ')" />
      <!-- Disabled records are hidden by default: they are usually noise, but they
           still have to be findable to be re-enabled. -->
      <FormControl
        v-if="hasDisabledFlag"
        type="checkbox"
        label="Show disabled"
        :modelValue="showDisabled"
        @update:modelValue="onShowDisabled"
      />
      <Button v-if="search || statusValue || showDisabled" label="Clear" @click="clearFilters" />
    </div>

    <!-- Pull-to-refresh indicator (mobile) -->
    <div
      v-if="ptrDistance || ptrRefreshing"
      class="flex items-center justify-center overflow-hidden text-ink-gray-5"
      :style="{ height: (ptrRefreshing ? 36 : ptrDistance) + 'px' }"
    >
      <Spinner v-if="ptrRefreshing" class="h-4 w-4" />
      <ArrowDown v-else class="h-4 w-4 transition-transform" :style="{ transform: `rotate(${Math.min((ptrDistance / 64) * 180, 180)}deg)` }" />
    </div>

    <!-- Loading skeleton -->
    <div v-if="list.loading && !rows.length" class="min-h-0 flex-1 space-y-2 overflow-hidden rounded-lg border border-outline-gray-1 bg-surface-white p-3">
      <Skeleton v-for="n in 12" :key="n" class="h-9 w-full" />
    </div>

    <!-- Mobile: stacked cards — everything fits, no horizontal scrolling -->
    <div
      v-else-if="isMobile"
      class="min-h-0 flex-1 overflow-y-auto rounded-lg border border-outline-gray-1 bg-surface-white"
    >
      <div v-if="!rows.length" class="p-8 text-center text-sm text-ink-gray-5">Nothing here yet.</div>
      <button
        v-for="row in rows"
        :key="row.name"
        class="flex w-full items-start justify-between gap-3 border-b border-outline-gray-1 px-3 py-3 text-left last:border-0 active:bg-surface-gray-2"
        @click="openDoc(row)"
      >
        <div class="min-w-0 flex-1">
          <div class="truncate text-sm font-medium text-ink-gray-8">{{ row[nameField] }}</div>
          <div v-if="subtitle(row)" class="mt-0.5 truncate text-xs text-ink-gray-5">{{ subtitle(row) }}</div>
        </div>
        <div class="flex shrink-0 flex-col items-end gap-1">
          <span v-if="amountField" class="text-sm font-medium tabular-nums text-ink-gray-8">
            {{ fmtCurrency(row[amountField], row[currencyField]) }}
          </span>
          <Badge v-if="statusField" :theme="statusTheme(row[statusField])" :label="row[statusField] || 'Draft'" />
          <!-- Doctypes without a status field still get their draft/submitted state shown -->
          <Badge
            v-else-if="row.docstatus !== undefined"
            :theme="docstatusBadge(row.docstatus).theme"
            :label="docstatusBadge(row.docstatus).label"
          />
          <Badge v-if="kindField && row[kindField]" :theme="kindTheme(row[kindField])" :label="row[kindField]" />
        </div>
      </button>
    </div>

    <!-- Desktop: full table -->
    <ListView
      v-else
      class="kamil-list min-h-0 flex-1 rounded-lg border border-outline-gray-1 bg-surface-white"
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
        <Badge v-if="column.type === 'status'" :theme="statusTheme(item)" :label="item || 'Draft'" />
        <Badge
          v-else-if="column.type === 'docstatus'"
          :theme="docstatusBadge(item).theme"
          :label="docstatusBadge(item).label"
        />
        <Badge v-else-if="column.type === 'kind' && item" :theme="kindTheme(item)" :label="item" />
        <span v-else-if="column.type === 'currency'" class="tabular-nums text-ink-gray-7">
          {{ fmtCurrency(item, row[currencyField]) }}
        </span>
        <span v-else-if="column.type === 'date'" class="text-ink-gray-6">{{ fmtDate(item) }}</span>
        <span v-else-if="column.type === 'ago'" class="text-ink-gray-5" :title="fmtDateTime(item)">{{ ago(item) }}</span>
        <span v-else :class="column.key === 'name' ? 'font-medium text-ink-gray-8' : 'text-ink-gray-7'">
          {{ item }}
        </span>
      </template>
    </ListView>

    <CreateDialog v-if="createConfig" v-model="showCreate" :config="createConfig" @created="onCreated" />
    <PaymentDialog v-if="special === 'payment'" v-model="showPayment" @created="onCreated" />
    <PaymentRequestDialog v-if="special === 'payment-request'" v-model="showRequest" @created="onCreated" />
    <!-- "Create Sales Invoice" off an order opens here, prefilled with the mapping -->
    <CreateDialog
      v-if="transfer.config"
      v-model="showTransfer"
      :config="transfer.config"
      :prefill="transfer.values"
      @created="onTransferred"
    />
    <DocViewDialog
      v-model="showView"
      :doctype="doctype"
      :name="viewName"
      :columns="viewFields || columns"
      :child="createConfig?.child || null"
      :currency-field="currencyField"
      @submitted="onCreated"
      @create-from="openTransfer"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Button, Badge, FormControl, ListView, Spinner, TextInput, createListResource, call, debounce } from 'frappe-ui'
import Plus from '~icons/lucide/plus'
import ArrowDown from '~icons/lucide/arrow-down'
import CreateDialog from '@/components/dialogs/CreateDialog.vue'
import PaymentDialog from '@/components/dialogs/PaymentDialog.vue'
import PaymentRequestDialog from '@/components/dialogs/PaymentRequestDialog.vue'
import DocViewDialog from '@/components/dialogs/DocViewDialog.vue'
import { useIsMobile } from '@/composables/useIsMobile'
import { usePullToRefresh } from '@/composables/usePullToRefresh'
import Skeleton from '@/components/Skeleton.vue'
import ComboField from '@/components/ComboField.vue'
import StatCard from '@/components/StatCard.vue'
import { haptic } from '@/utils/haptics'
import { statusTheme, docstatusBadge, kindTheme } from '@/utils/status.js'
import { defaultCurrency } from '@/utils/money.js'

const props = defineProps({
  title: { type: String, required: true },
  doctype: { type: String, required: true },
  columns: { type: Array, required: true },
  // What the viewer shows; falls back to the list columns when a doctype has no
  // richer set declared.
  viewFields: { type: Array, default: null },
  filters: { type: Object, default: () => ({}) },
  orderBy: { type: String, default: 'modified desc' },
  currencyField: { type: String, default: 'currency' },
  createConfig: { type: Object, default: null },
  special: { type: String, default: '' },
})

const rootEl = ref(null)
const showCreate = ref(false)
const showPayment = ref(false)
const showRequest = ref(false)
const showView = ref(false)
const viewName = ref('')
// A document mapped from another one, waiting to be reviewed and saved.
const showTransfer = ref(false)
const transfer = ref({ config: null, values: null })

const isMobile = useIsMobile()

const kpis = ref([])
const kpiCurrency = ref('')
async function loadKpis() {
  try {
    const r = await call('kamil.api.get_list_kpis', { doctype: props.doctype })
    kpis.value = r?.kpis || []
    kpiCurrency.value = r?.currency || defaultCurrency()
  } catch (e) {
    kpis.value = []
  }
}
onMounted(loadKpis)
function kpiValue(k) {
  return k.money ? fmtCurrency(k.value, kpiCurrency.value) : new Intl.NumberFormat('en-KE').format(k.value || 0)
}

const SPECIAL_LABELS = { payment: 'New Payment', 'payment-request': 'Request Payment' }
const canCreate = computed(() => !!props.createConfig || !!SPECIAL_LABELS[props.special])
const newLabel = computed(
  () => SPECIAL_LABELS[props.special] || 'New ' + (props.createConfig?.label || 'Record'),
)

// Field roles derived from the column config (drives the mobile card layout)
const pick = (fn) => computed(() => (props.columns.find(fn) || {}).field || '')
const nameField = pick((c) => c.field === 'name')
const statusField = pick((c) => c.type === 'status')
const amountField = pick((c) => c.type === 'currency')
const dateField = pick((c) => c.type === 'date')
const kindField = pick((c) => c.type === 'kind')
const partyField = pick((c) => !c.type && c.field !== 'name')

function subtitle(row) {
  const parts = []
  if (partyField.value && row[partyField.value]) parts.push(row[partyField.value])
  if (dateField.value && row[dateField.value]) parts.push(fmtDate(row[dateField.value]))
  if (row.modified) parts.push(ago(row.modified))
  return parts.join(' · ')
}

function openNew() {
  haptic()
  if (props.special === 'payment') showPayment.value = true
  else if (props.special === 'payment-request') showRequest.value = true
  else showCreate.value = true
}
function onCreated() {
  list.reload()
  loadKpis()
}

const queryFields = computed(() => {
  // docstatus is always fetched so lists without a status field can still show state.
  const set = new Set(['name', 'docstatus'])
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

const { distance: ptrDistance, refreshing: ptrRefreshing } = usePullToRefresh(rootEl, () => {
  list.reload()
  return new Promise((r) => setTimeout(r, 700))
})

const route = useRoute()
const search = ref('')
// May arrive from a notification deep-link as a comma-separated set ("Unpaid,Partly Paid"),
// in which case we filter on all of them so the list matches the count that was clicked.
const statusValue = ref(String(route.query.status || ''))
const statusOptions = ref([])
// Whether this doctype even has the flag — asked once, from the same metadata the
// forms use.
const hasDisabledFlag = ref(false)
const showDisabled = ref(false)
const statusList = computed(() => statusValue.value.split(',').map((s) => s.trim()).filter(Boolean))
// The dropdown can only represent a single selection.
const comboStatus = computed(() => (statusList.value.length === 1 ? statusList.value[0] : ''))

async function loadStatuses() {
  try {
    statusOptions.value = (await call('kamil.api.get_status_options', { doctype: props.doctype })) || []
  } catch (e) {
    statusOptions.value = []
  }
}
async function loadDisabledFlag() {
  try {
    const meta = await call('kamil.api.get_form_field_meta', {
      doctype: props.doctype,
      fieldnames: JSON.stringify(['disabled']),
    })
    hasDisabledFlag.value = !!meta?.disabled
    if (hasDisabledFlag.value) applyFilters()
  } catch (e) {
    hasDisabledFlag.value = false
  }
}

onMounted(() => {
  loadDisabledFlag()
  loadStatuses()
  // A deep-linked status has to be pushed into the resource, which was created
  // before we looked at the query string.
  if (statusList.value.length) applyFilters()
})

// Clicking a second notification for the same list only changes the query string.
watch(
  () => route.query.status,
  (v) => {
    const next = String(v || '')
    if (next === statusValue.value) return
    statusValue.value = next
    applyFilters()
  },
)

function applyFilters() {
  const f = { ...props.filters }
  if (hasDisabledFlag.value && !showDisabled.value) f.disabled = 0
  if (statusList.value.length === 1) f.status = statusList.value[0]
  else if (statusList.value.length > 1) f.status = ['in', statusList.value]
  list.filters = f

  const q = (search.value || '').trim()
  const ors = []
  if (q) {
    ors.push(['name', 'like', `%${q}%`])
    if (partyField.value) ors.push([partyField.value, 'like', `%${q}%`])
  }
  list.orFilters = ors.length ? ors : null

  list.start = 0
  list.reload()
}
const debouncedApply = debounce(applyFilters, 350)
function onSearchInput(v) {
  search.value = v ?? ''
  debouncedApply()
}
function onStatus(v) {
  statusValue.value = v || ''
  applyFilters()
}
function clearFilters() {
  search.value = ''
  statusValue.value = ''
  showDisabled.value = false
  applyFilters()
}

function onShowDisabled(value) {
  showDisabled.value = !!value
  applyFilters()
}

function openTransfer({ config, values }) {
  transfer.value = { config, values }
  showTransfer.value = true
}

function onTransferred() {
  showTransfer.value = false
  onCreated()
}

function openDoc(row) {
  haptic()
  viewName.value = row.name
  showView.value = true
}
function fmtCurrency(v, currency) {
  if (v === null || v === undefined) return ''
  try {
    return new Intl.NumberFormat('en-KE', { style: 'currency', currency: currency || defaultCurrency(), maximumFractionDigits: 0 }).format(v)
  } catch {
    return v
  }
}
function fmtDate(v) {
  if (!v) return ''
  return new Date(v).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}
function fmtDateTime(v) {
  if (!v) return ''
  return new Date(String(v).replace(' ', 'T')).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}
// "3 minutes ago" reads faster than a timestamp when scanning a list; the exact time
// is still there on hover.
function ago(v) {
  if (!v) return ''
  const then = new Date(String(v).replace(' ', 'T')).getTime()
  if (!Number.isFinite(then)) return ''
  const secs = Math.round((Date.now() - then) / 1000)
  if (secs < 45) return 'just now'
  const units = [
    ['minute', 60],
    ['hour', 3600],
    ['day', 86400],
    ['week', 604800],
    ['month', 2592000],
    ['year', 31536000],
  ]
  let label = 'year'
  let size = 31536000
  for (let i = 0; i < units.length; i++) {
    const next = units[i + 1]
    if (!next || secs < next[1]) {
      label = units[i][0]
      size = units[i][1]
      break
    }
  }
  const n = Math.max(1, Math.round(secs / size))
  return `${n} ${label}${n > 1 ? 's' : ''} ago`
}
</script>
