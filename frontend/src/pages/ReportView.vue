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

    <div v-if="partyFilter.party || hiddenCount" class="flex flex-wrap items-center gap-2">
      <Badge v-if="partyFilter.party" theme="blue" :label="`${partyFilter.party_type || 'Party'}: ${partyFilter.party[0]}`" />
      <Button v-if="partyFilter.party" label="Clear filter" @click="clearParty" />
      <Badge v-if="hiddenCount" theme="gray" :label="`${hiddenCount} column${hiddenCount > 1 ? 's' : ''} hidden`" />
      <Button v-if="hiddenCount" label="Show all columns" @click="showAllColumns" />
    </div>

    <div v-if="loading" class="space-y-2">
      <Skeleton v-for="n in 12" :key="n" class="h-8 w-full" />
    </div>
    <div v-else-if="error" class="rounded-lg border border-outline-gray-1 bg-surface-white p-6 text-center text-sm text-red-600">
      {{ error }}
    </div>
    <div v-else class="min-h-0 flex-1 overflow-auto rounded-lg border border-outline-gray-1 bg-surface-white">
      <table class="w-full text-sm">
        <thead class="sticky top-0 z-10 bg-surface-gray-2">
          <tr>
            <th
              v-for="c in visibleColumns"
              :key="c.fieldname"
              class="whitespace-nowrap px-3 py-2 text-xs font-medium text-ink-gray-5"
              :class="isNum(c) ? 'text-right' : 'text-left'"
            >
              {{ c.label }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in rows" :key="i" class="border-t border-outline-gray-1">
            <td
              v-for="c in visibleColumns"
              :key="c.fieldname"
              class="whitespace-nowrap px-3 py-1.5 text-ink-gray-7"
              :class="isNum(c) ? 'text-right tabular-nums' : ''"
            >
              {{ fmt(r[c.fieldname], c) }}
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td :colspan="Math.max(visibleColumns.length, 1)" class="p-8 text-center text-sm text-ink-gray-5">
              No data for this period.
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="truncated" class="text-xs text-ink-gray-5">Showing the first 500 rows.</div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { Button, FormControl, Dropdown, Badge, call } from 'frappe-ui'
import Download from '~icons/lucide/download'
import Columns from '~icons/lucide/columns'
import Skeleton from '@/components/Skeleton.vue'
import ComboField from '@/components/ComboField.vue'
import LinkField from '@/components/LinkField.vue'
import { findReport } from '@/data/reports.js'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const cfg = computed(() => findReport(route.params.key))

// Party drill-down passed via the query string (?party_type=Customer&party=A/002).
// General Ledger expects `party` as a LIST.
const partyFilter = computed(() => {
  const q = route.query || {}
  if (!q.party) return {}
  return {
    party_type: q.party_type || '',
    party: Array.isArray(q.party) ? q.party : [q.party],
  }
})
function clearParty() {
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
const hidden = ref(new Set())
const storageKey = computed(() => `kamil:report-columns:${route.params.key}`)

function loadHidden() {
  try {
    const raw = localStorage.getItem(storageKey.value)
    hidden.value = new Set(raw ? JSON.parse(raw) : [])
  } catch (e) {
    hidden.value = new Set()
  }
}
function persistHidden() {
  try {
    localStorage.setItem(storageKey.value, JSON.stringify([...hidden.value]))
  } catch (e) {
    /* private browsing — visibility just won't persist */
  }
}
function toggleColumn(fieldname) {
  const next = new Set(hidden.value)
  if (next.has(fieldname)) next.delete(fieldname)
  else next.add(fieldname)
  // Never let the last column be hidden — the table would be unreadable.
  if (next.size >= columns.value.length) return
  hidden.value = next
  persistHidden()
}
function showAllColumns() {
  hidden.value = new Set()
  persistHidden()
}

const visibleColumns = computed(() => columns.value.filter((c) => !hidden.value.has(c.fieldname)))
const hiddenCount = computed(() => columns.value.length - visibleColumns.value.length)

// Checkbox-style menu: a tick against every column that is currently shown.
const columnOptions = computed(() => [
  {
    group: 'Show columns',
    items: columns.value.map((c) => ({
      label: `${hidden.value.has(c.fieldname) ? '☐' : '☑'}  ${c.label || c.fieldname}`,
      onClick: () => toggleColumn(c.fieldname),
    })),
  },
])

// --- running the report -------------------------------------------------------
function payload() {
  return JSON.stringify({ ...(cfg.value?.defaults || {}), ...values, ...partyFilter.value })
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
  () => [route.params.key, route.query.party, route.query.party_type],
  ([key], old) => {
    if (!old || old[0] !== key) {
      applyDefaults()
      loadHidden()
    }
    run()
  },
  { immediate: true },
)

const downloadOptions = [
  { label: 'CSV', onClick: () => downloadCsv() },
  { label: 'Excel (.xlsx)', onClick: () => downloadExcel() },
]

function fileStamp() {
  return `${(cfg.value?.title || 'report').replace(/\s+/g, '-')}-${today()}`
}

// Downloads follow what is on screen — hidden columns are left out.
function downloadCsv() {
  const esc = (v) => {
    const str = v === null || v === undefined ? '' : String(v)
    return /[",\n]/.test(str) ? `"${str.replace(/"/g, '""')}"` : str
  }
  const cols = visibleColumns.value
  const head = cols.map((c) => esc(c.label)).join(',')
  const body = rows.value.map((r) => cols.map((c) => esc(r[c.fieldname])).join(',')).join('\n')
  // BOM keeps Excel happy with UTF-8
  const blob = new Blob(['\uFEFF' + head + '\n' + body], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${fileStamp()}.csv`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

function downloadExcel() {
  const q = new URLSearchParams({
    report: cfg.value?.report || '',
    filters: payload(),
    file_format: 'Excel',
  })
  if (hiddenCount.value) q.set('columns', JSON.stringify(visibleColumns.value.map((c) => c.fieldname)))
  window.open(`/api/method/kamil.api.export_report?${q.toString()}`, '_blank')
}

function isNum(c) {
  return ['Currency', 'Float', 'Int', 'Percent'].includes(c.fieldtype)
}
function fmt(v, c) {
  if (v === null || v === undefined || v === '') return ''
  if (c.fieldtype === 'Currency') {
    try {
      return new Intl.NumberFormat('en-KE', { style: 'currency', currency: currency.value || 'KES', maximumFractionDigits: 0 }).format(v)
    } catch {
      return v
    }
  }
  if (c.fieldtype === 'Float' || c.fieldtype === 'Percent') return Number(v).toLocaleString('en-KE', { maximumFractionDigits: 2 })
  if (c.fieldtype === 'Int') return Number(v).toLocaleString('en-KE')
  if (c.fieldtype === 'Date') return new Date(v).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
  return typeof v === 'string' ? v.replace(/<[^>]*>/g, '') : v
}
</script>
