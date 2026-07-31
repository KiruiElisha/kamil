<template>
  <div class="flex min-h-0 flex-1 flex-col gap-3">
    <div class="flex flex-wrap items-end justify-between gap-2">
      <div class="flex flex-wrap items-end gap-2">
        <template v-for="f in cfg?.filters || []" :key="f.fieldname">
          <FormControl
            v-if="f.fieldtype === 'date'"
            type="date"
            :label="f.label"
            v-model="values[f.fieldname]"
          />
          <ComboField
            v-else-if="f.fieldtype === 'select'"
            class="w-40"
            :label="f.label"
            :options="f.options"
            :modelValue="values[f.fieldname]"
            @update:modelValue="(v) => (values[f.fieldname] = v || '')"
          />
          <LinkField
            v-else-if="f.fieldtype === 'link'"
            class="w-48"
            :label="f.label"
            :doctype="f.options"
            :filters="f.filters || {}"
            :modelValue="values[f.fieldname]"
            @update:modelValue="(v) => (values[f.fieldname] = v || '')"
          />
        </template>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <Dropdown v-if="columns.length" :options="columnOptions">
          <Button label="Columns">
            <template #prefix><Columns class="h-4 w-4" /></template>
          </Button>
        </Dropdown>
        <Button variant="solid" label="Run" :loading="loading" @click="run" />
        <Button label="Open full report" @click="openFull" />
      </div>
    </div>

    <div v-if="party" class="flex flex-wrap items-center gap-2">
      <Badge theme="blue" :label="`${partyType}: ${party}`" />
      <Button label="Show all" @click="clearParty" />
    </div>

    <ReportTable
      :columns="visibleColumns"
      :rows="rows"
      :currency="currency"
      :loading="loading"
      :error="error"
      @drill="onDrill"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Button, Badge, Dropdown, FormControl, call } from 'frappe-ui'
import Columns from '~icons/lucide/columns'
import ComboField from '@/components/ComboField.vue'
import LinkField from '@/components/LinkField.vue'
import ReportTable from '@/components/ReportTable.vue'
import { useReportColumns } from '@/composables/useReportColumns'
import { findReport, buildFilters } from '@/data/reports.js'
import { defaultCurrency } from '@/utils/money.js'

const props = defineProps({
  // A report key from data/reports.js — this tab is that report, embedded.
  reportKey: { type: String, required: true },
  // When set, the tab drills into one party instead of showing everybody.
  partyType: { type: String, default: '' },
})

const router = useRouter()
const cfg = computed(() => findReport(props.reportKey))

const values = reactive({})
const columns = ref([])
const rows = ref([])
const currency = ref('')
const loading = ref(false)
const error = ref('')
const party = ref('')

const storageKey = computed(() => `kamil:list-report-columns:${props.reportKey}`)
const { visibleColumns, columnOptions } = useReportColumns(columns, storageKey)

function today() {
  return new Date().toISOString().slice(0, 10)
}
function monthStart() {
  const d = new Date()
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10)
}
function yearStart() {
  return new Date(new Date().getFullYear(), 0, 1).toISOString().slice(0, 10)
}

// Only the date-ish tokens matter here: these are ledger and outstanding reports, not
// the fiscal-year statements.
function resolveDefault(token) {
  if (token === 'today') return today()
  if (token === 'month_start') return monthStart()
  if (token === 'year_start' || token === 'fiscal_year_start') return yearStart()
  return token ?? ''
}

function applyDefaults() {
  Object.keys(values).forEach((k) => delete values[k])
  for (const f of cfg.value?.filters || []) values[f.fieldname] = resolveDefault(f.default)
}

async function run() {
  if (!cfg.value) return
  loading.value = true
  error.value = ''
  try {
    // General Ledger takes its party as a list; buildFilters does the same wrapping
    // for every other multi-select filter the report declares.
    const extra = party.value && props.partyType
      ? { party_type: props.partyType, party: [party.value] }
      : {}
    const filters = buildFilters(cfg.value, values, extra)
    const res = await call('kamil.api.run_report', {
      report: cfg.value.report,
      filters: JSON.stringify(filters),
      limit: 500,
    })
    columns.value = res?.columns || []
    rows.value = res?.rows || []
    currency.value = res?.currency || defaultCurrency()
  } catch (e) {
    error.value = (e?.messages?.join(', ') || e?.message || 'Could not run this report.').replace(/<[^>]*>/g, '')
    columns.value = []
    rows.value = []
  } finally {
    loading.value = false
  }
}

/** Clicking a party in the outstanding report narrows this tab to their ledger. */
function onDrill({ target, value }) {
  if (target === 'Account') {
    router.push({ path: '/report/general-ledger', query: { account: value } })
    return
  }
  router.push({ path: '/report/general-ledger', query: { party_type: target, party: value } })
}

function clearParty() {
  party.value = ''
  run()
}

function openFull() {
  const query = party.value ? { party_type: props.partyType, party: party.value } : {}
  router.push({ path: `/report/${props.reportKey}`, query })
}

watch(
  () => props.reportKey,
  () => {
    applyDefaults()
    run()
  },
  { immediate: true },
)

defineExpose({ setParty: (p) => ((party.value = p), run()) })
</script>
