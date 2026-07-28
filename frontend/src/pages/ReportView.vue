<template>
  <div class="mx-auto flex w-full min-h-0 max-w-6xl flex-1 flex-col gap-3 p-3 md:p-5">
    <div class="flex flex-wrap items-end justify-between gap-2">
      <h2 class="text-lg font-semibold text-ink-gray-8">{{ cfg?.title || 'Report' }}</h2>
      <div class="flex flex-wrap items-end gap-2">
        <!-- Filters, rendered from each report's own declaration -->
        <template v-for="f in cfg?.filters || []" :key="f.fieldname">
          <FormControl
            v-if="f.fieldtype === 'date'"
            type="date"
            :label="f.label"
            v-model="values[f.fieldname]"
          />
          <FormControl
            v-else-if="f.fieldtype === 'check'"
            type="checkbox"
            :label="f.label"
            :modelValue="!!values[f.fieldname]"
            @update:modelValue="(v) => (values[f.fieldname] = v ? 1 : 0)"
          />
          <ComboField
            v-else-if="f.fieldtype === 'select'"
            class="w-40"
            :label="f.label"
            :options="f.options"
            :modelValue="values[f.fieldname]"
            @update:modelValue="(v) => (values[f.fieldname] = v || '')"
          />
          <ComboField
            v-else-if="f.fieldtype === 'fiscal_year'"
            class="w-40"
            :label="f.label"
            :options="fiscalYears"
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

        <Dropdown v-if="columns.length" :options="columnOptions">
          <Button label="Columns">
            <template #prefix><Columns class="h-4 w-4" /></template>
          </Button>
        </Dropdown>
        <Dropdown :options="downloadOptions">
          <Button label="Download" :disabled="!rows.length">
            <template #prefix><Download class="h-4 w-4" /></template>
          </Button>
        </Dropdown>
        <Button variant="solid" label="Run" :loading="loading" @click="run" />
      </div>
    </div>

    <div v-if="drillFilter.party || drillFilter.account || hiddenCount" class="flex flex-wrap items-center gap-2">
      <Badge
        v-if="drillFilter.party"
        theme="blue"
        :label="`${drillFilter.party_type || 'Party'}: ${drillFilter.party[0]}`"
      />
      <Badge v-if="drillFilter.account" theme="blue" :label="`Account: ${drillFilter.account[0]}`" />
      <Button v-if="drillFilter.party || drillFilter.account" label="Clear filter" @click="clearDrill" />
      <Badge v-if="hiddenCount" theme="gray" :label="`${hiddenCount} column${hiddenCount > 1 ? 's' : ''} hidden`" />
      <Button v-if="hiddenCount" label="Show all columns" @click="showAllColumns" />
    </div>

    <ReportTable
      :columns="visibleColumns"
      :rows="rows"
      :currency="currency"
      :loading="loading"
      :error="error"
      @drill="openLedger"
    />

    <div v-if="truncated" class="text-xs text-ink-gray-5">Showing the first 500 rows.</div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { Button, FormControl, Dropdown, Badge, call } from 'frappe-ui'
import Download from '~icons/lucide/download'
import Columns from '~icons/lucide/columns'
import ComboField from '@/components/ComboField.vue'
import LinkField from '@/components/LinkField.vue'
import ReportTable from '@/components/ReportTable.vue'
import { useReportColumns } from '@/composables/useReportColumns'
import { csvFor, downloadBlob } from '@/utils/reportFormat.js'
import { findReport } from '@/data/reports.js'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const cfg = computed(() => findReport(route.params.key))

// Drill-down passed via the query string — either a party
// (?party_type=Customer&party=A/002) or an account (?account=Debtors - KE).
// General Ledger expects both as LISTS.
const drillFilter = computed(() => {
  const q = route.query || {}
  const out = {}
  if (q.party) {
    out.party_type = q.party_type || ''
    out.party = Array.isArray(q.party) ? q.party : [q.party]
  }
  if (q.account) out.account = Array.isArray(q.account) ? q.account : [q.account]
  return out
})
function clearDrill() {
  router.replace({ path: route.path })
}

const values = reactive({})
const columns = ref([])
const rows = ref([])
const currency = ref('KES')
const truncated = ref(false)
const loading = ref(false)
const error = ref('')

// --- fiscal year, fetched once and shared by every report that needs it -------
const fiscalYears = ref([])
const fiscalYear = ref({ name: null, start_date: null, end_date: null })

onMounted(async () => {
  try {
    const [years, current] = await Promise.all([
      call('kamil.api.get_fiscal_years'),
      call('kamil.api.get_current_fiscal_year'),
    ])
    fiscalYears.value = years || []
    fiscalYear.value = current || fiscalYear.value
    // Defaults were applied before this resolved, so fill in anything still blank
    // and re-run if a filter the report needs has only now become available.
    let filled = false
    for (const f of cfg.value?.filters || []) {
      if (!values[f.fieldname]) {
        values[f.fieldname] = resolveDefault(f.default)
        if (values[f.fieldname]) filled = true
      }
    }
    if (filled) run()
  } catch (e) {
    /* filters keep their calendar-based fallbacks */
  }
})

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

function resolveDefault(token) {
  switch (token) {
    case 'month_start':
      return monthStart()
    case 'year_start':
      return yearStart()
    case 'fiscal_year_start':
      return fiscalYear.value.start_date || yearStart()
    case 'fiscal_year':
      return fiscalYear.value.name || ''
    case 'today':
      return today()
    default:
      // Anything else is a literal — a select's default value, or 0/1 for a check.
      return token ?? ''
  }
}

function applyDefaults() {
  Object.keys(values).forEach((k) => delete values[k])
  for (const f of cfg.value?.filters || []) {
    values[f.fieldname] = resolveDefault(f.default)
  }
}

// --- column visibility, remembered per report --------------------------------
const storageKey = computed(() => `kamil:report-columns:${route.params.key}`)
const { visibleColumns, hiddenCount, columnOptions, showAllColumns } = useReportColumns(columns, storageKey)

// --- running the report -------------------------------------------------------
function payload() {
  return JSON.stringify({ ...(cfg.value?.defaults || {}), ...values, ...drillFilter.value })
}

async function run() {
  if (!cfg.value) return
  loading.value = true
  error.value = ''
  try {
    const res = await call('kamil.api.run_report', {
      report: cfg.value.report,
      filters: payload(),
      limit: 500,
    })
    columns.value = res?.columns || []
    rows.value = res?.rows || []
    currency.value = res?.currency || 'KES'
    truncated.value = !!res?.truncated
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not run this report.'
    columns.value = []
    rows.value = []
  } finally {
    loading.value = false
  }
}

watch(
  () => [route.params.key, route.query.party, route.query.party_type, route.query.account],
  ([key], old) => {
    if (!old || old[0] !== key) applyDefaults()
    run()
  },
  { immediate: true },
)

/** A party or account cell was clicked — open its ledger. */
function openLedger({ target, value }) {
  const query = target === 'Account' ? { account: value } : { party_type: target, party: value }
  router.push({ path: '/report/general-ledger', query })
}

const downloadOptions = [
  { label: 'CSV', onClick: () => downloadCsv() },
  { label: 'Excel (.xlsx)', onClick: () => serverDownload('Excel') },
  { label: 'PDF', onClick: () => serverDownload('PDF') },
]

function fileStamp() {
  return `${(cfg.value?.title || 'report').replace(/\s+/g, '-')}-${today()}`
}

// Downloads follow what is on screen — hidden columns are left out.
function downloadCsv() {
  downloadBlob(csvFor(visibleColumns.value, rows.value), `${fileStamp()}.csv`)
}

function serverDownload(format) {
  const q = new URLSearchParams({
    report: cfg.value?.report || '',
    filters: payload(),
    file_format: format,
  })
  if (hiddenCount.value) q.set('columns', JSON.stringify(visibleColumns.value.map((c) => c.fieldname)))
  window.open(`/api/method/kamil.api.export_report?${q.toString()}`, '_blank')
}
</script>
