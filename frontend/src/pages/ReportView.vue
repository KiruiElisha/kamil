<template>
  <div class="mx-auto flex w-full min-h-0 max-w-6xl flex-1 flex-col gap-3 p-3 md:p-5">
    <div class="flex flex-wrap items-end justify-between gap-2">
      <h2 class="text-lg font-semibold text-ink-gray-8">{{ cfg?.title || 'Report' }}</h2>
      <div class="flex flex-wrap items-end gap-2">
        <FormControl
          v-for="f in cfg?.filters || []"
          :key="f.fieldname"
          type="date"
          :label="f.label"
          v-model="values[f.fieldname]"
        />
        <Dropdown :options="downloadOptions">
          <Button label="Download" :disabled="!rows.length">
            <template #prefix><Download class="h-4 w-4" /></template>
          </Button>
        </Dropdown>
        <Button variant="solid" label="Run" :loading="loading" @click="run" />
      </div>
    </div>

    <div v-if="partyFilter.party" class="flex flex-wrap items-center gap-2">
      <Badge theme="blue" :label="`${partyFilter.party_type || 'Party'}: ${partyFilter.party[0]}`" />
      <Button label="Clear filter" @click="clearParty" />
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
              v-for="c in columns"
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
              v-for="c in columns"
              :key="c.fieldname"
              class="whitespace-nowrap px-3 py-1.5 text-ink-gray-7"
              :class="isNum(c) ? 'text-right tabular-nums' : ''"
            >
              {{ fmt(r[c.fieldname], c) }}
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td :colspan="Math.max(columns.length, 1)" class="p-8 text-center text-sm text-ink-gray-5">
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
import { ref, reactive, computed, watch } from 'vue'
import { Button, FormControl, Dropdown, Badge, call } from 'frappe-ui'
import Download from '~icons/lucide/download'
import Skeleton from '@/components/Skeleton.vue'
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

function today() {
  return new Date().toISOString().slice(0, 10)
}
function monthStart() {
  const d = new Date()
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10)
}

function applyDefaults() {
  Object.keys(values).forEach((k) => delete values[k])
  for (const f of cfg.value?.filters || []) {
    values[f.fieldname] = f.default === 'month_start' ? monthStart() : today()
  }
}

async function run() {
  if (!cfg.value) return
  loading.value = true
  error.value = ''
  try {
    const res = await call('kamil.api.run_report', {
      report: cfg.value.report,
      filters: JSON.stringify({ ...values, ...partyFilter.value }),
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
    if (!old || old[0] !== key) applyDefaults()
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

function downloadCsv() {
  const esc = (v) => {
    const str = v === null || v === undefined ? '' : String(v)
    return /[",\n]/.test(str) ? `"${str.replace(/"/g, '""')}"` : str
  }
  const head = columns.value.map((c) => esc(c.label)).join(',')
  const body = rows.value
    .map((r) => columns.value.map((c) => esc(r[c.fieldname])).join(','))
    .join('\n')
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
    filters: JSON.stringify({ ...values, ...partyFilter.value }),
    file_format: 'Excel',
  })
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
