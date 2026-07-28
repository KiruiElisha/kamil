<template>
  <div class="flex min-h-0 flex-1 flex-col gap-3">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h3 class="text-sm font-semibold text-ink-gray-8">{{ title }} report</h3>
      <div class="flex flex-wrap items-center gap-2">
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
        <Button label="Refresh" :loading="loading" @click="load" />
      </div>
    </div>

    <div v-if="hiddenCount" class="flex flex-wrap items-center gap-2">
      <Badge theme="gray" :label="`${hiddenCount} column${hiddenCount > 1 ? 's' : ''} hidden`" />
      <Button label="Show all columns" @click="showAllColumns" />
    </div>

    <ReportTable
      :columns="visibleColumns"
      :rows="rows"
      :currency="currency"
      :totals="visibleTotals"
      :loading="loading"
      :error="error"
      empty-text="Nothing to report yet."
      @drill="openLedger"
    />

    <div v-if="truncated" class="text-xs text-ink-gray-5">Showing the most recent 200 records.</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Button, Badge, Dropdown, call } from 'frappe-ui'
import Download from '~icons/lucide/download'
import Columns from '~icons/lucide/columns'
import ReportTable from '@/components/ReportTable.vue'
import { useReportColumns } from '@/composables/useReportColumns'
import { csvFor, downloadBlob } from '@/utils/reportFormat.js'

const props = defineProps({
  doctype: { type: String, required: true },
  title: { type: String, default: '' },
})

const router = useRouter()

const columns = ref([])
const rows = ref([])
const totals = ref({})
const currency = ref('KES')
const truncated = ref(false)
const loading = ref(false)
const error = ref('')

const storageKey = computed(() => `kamil:doc-report-columns:${props.doctype}`)
const { visibleColumns, hiddenCount, columnOptions, showAllColumns } = useReportColumns(columns, storageKey)

// Only total the columns that are actually on screen.
const visibleTotals = computed(() =>
  Object.fromEntries(
    Object.entries(totals.value || {}).filter(([fieldname]) =>
      visibleColumns.value.some((c) => c.fieldname === fieldname),
    ),
  ),
)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await call('kamil.api.get_doc_report', { doctype: props.doctype, limit: 200 })
    columns.value = res?.columns || []
    rows.value = res?.rows || []
    totals.value = res?.totals || {}
    currency.value = res?.currency || 'KES'
    truncated.value = !!res?.truncated
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not build this report.'
    columns.value = []
    rows.value = []
  } finally {
    loading.value = false
  }
}
onMounted(load)

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
  return `${props.doctype.replace(/\s+/g, '-')}-${new Date().toISOString().slice(0, 10)}`
}

function downloadCsv() {
  downloadBlob(csvFor(visibleColumns.value, rows.value), `${fileStamp()}.csv`)
}

function serverDownload(format) {
  const q = new URLSearchParams({ doctype: props.doctype, file_format: format })
  if (hiddenCount.value) q.set('columns', JSON.stringify(visibleColumns.value.map((c) => c.fieldname)))
  window.open(`/api/method/kamil.api.export_doc_report?${q.toString()}`, '_blank')
}
</script>
