<template>
  <div class="mx-auto flex w-full min-h-0 max-w-6xl flex-1 flex-col gap-4 overflow-auto p-3 md:p-5">
    <div>
      <h2 class="text-lg font-semibold text-ink-gray-8">Bank statements</h2>
      <p class="mt-1 text-sm text-ink-gray-5">
        Upload a statement, check what it read, then create the bank transactions. Rows already
        on file are skipped, so re-uploading an overlapping statement cannot double-count.
      </p>
    </div>

    <!-- Pick the account and the file -->
    <div class="space-y-3 rounded-xl border border-outline-gray-1 bg-surface-white p-4">
      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <ComboField
          label="Bank account"
          :options="accountOptions"
          :modelValue="bankAccount"
          placeholder="Which account is this statement for?"
          @update:modelValue="(v) => (bankAccount = v || '')"
        />
        <div>
          <label class="mb-1 block text-xs text-ink-gray-5">Statement file (.csv or .xlsx)</label>
          <div class="flex items-center gap-2">
            <FileUploader @success="onUploaded">
              <template #default="{ openFileSelector, uploading }">
                <Button :loading="uploading || parsing" :label="fileName ? 'Replace file' : 'Choose file'" @click="openFileSelector()" />
              </template>
            </FileUploader>
            <span class="truncate text-xs text-ink-gray-6">{{ fileName || 'Nothing uploaded yet' }}</span>
          </div>
        </div>
      </div>

      <!-- One PDF can hold several accounts (Absa prints KES and USD together) -->
      <div v-if="sections.length > 1" class="space-y-2">
        <div class="text-xs text-ink-gray-5">This file holds {{ sections.length }} accounts — pick one:</div>
        <div class="flex flex-wrap gap-2">
          <Button
            v-for="(sec, i) in sections"
            :key="i"
            :variant="i === sectionIndex ? 'solid' : 'subtle'"
            :label="`${sec.label} · ${sec.rows.length} rows`"
            @click="pickSection(i)"
          />
        </div>
      </div>

      <div v-if="activeSection && !activeSection.balanced" class="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
        <div class="font-medium">This statement does not add up — check it before importing.</div>
        <div v-for="c in activeSection.checks" :key="c">{{ c }}</div>
      </div>
      <div v-else-if="activeSection?.warnings?.length" class="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
        <div class="font-medium">Read, but worth a look:</div>
        <div v-for="w in activeSection.warnings" :key="w">{{ w }}</div>
      </div>

      <div v-if="parseError" class="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
        {{ parseError }}
        <div v-if="sample.length" class="mt-2 space-y-1 text-xs">
          <div class="font-medium">First rows of the file, so you can see what it looks like:</div>
          <div v-for="(row, i) in sample" :key="i" class="truncate font-mono">{{ row.join(' | ') }}</div>
        </div>
      </div>
      <ErrorMessage :message="error" />
    </div>

    <!-- What the file said -->
    <div v-if="rows.length" class="space-y-3">
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Rows read" :value="String(rows.length)" icon="layers" color="blue" />
        <StatCard label="Money in" :value="money(totals.deposits)" icon="trending-up" color="green" />
        <StatCard label="Money out" :value="money(totals.withdrawals)" icon="wallet" color="red" />
        <StatCard label="Net" :value="money(totals.deposits - totals.withdrawals)" icon="calendar" color="violet" />
      </div>

      <div class="max-h-[45vh] overflow-auto rounded-lg border border-outline-gray-1 bg-surface-white">
        <table class="w-full text-sm">
          <thead class="sticky top-0 z-10">
            <tr class="bg-surface-gray-3 text-left text-[11px] uppercase tracking-wide text-ink-gray-6">
              <th class="px-3 py-2">Date</th>
              <th class="px-3 py-2">Description</th>
              <th class="px-3 py-2">Reference</th>
              <th class="px-3 py-2 text-right">In</th>
              <th class="px-3 py-2 text-right">Out</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(r, i) in rows"
              :key="i"
              class="border-b border-outline-gray-1 last:border-0"
              :class="i % 2 ? 'bg-surface-gray-1' : ''"
            >
              <td class="whitespace-nowrap px-3 py-1.5 text-ink-gray-7">{{ r.date }}</td>
              <td class="px-3 py-1.5 text-ink-gray-7">{{ r.description }}</td>
              <td class="whitespace-nowrap px-3 py-1.5 text-ink-gray-5">{{ r.reference_number }}</td>
              <td class="whitespace-nowrap px-3 py-1.5 text-right tabular-nums text-green-700">
                {{ r.deposit ? money(r.deposit) : '' }}
              </td>
              <td class="whitespace-nowrap px-3 py-1.5 text-right tabular-nums text-red-600">
                {{ r.withdrawal ? money(r.withdrawal) : '' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="result" class="space-y-1 rounded-lg border p-3 text-sm" :class="result.ok ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'">
        <div :class="result.ok ? 'font-medium text-green-700' : 'font-medium text-red-700'">{{ result.title }}</div>
        <div v-for="line in result.lines" :key="line" class="text-ink-gray-7">{{ line }}</div>
      </div>

      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="flex flex-wrap items-center gap-4">
          <FormControl type="checkbox" label="Submit transactions (leave off to keep them as drafts)" v-model="submitOnImport" />
          <FormControl
            v-if="activeSection && !activeSection.balanced"
            type="checkbox"
            label="Import anyway"
            v-model="importAnyway"
          />
        </div>
        <div class="flex gap-2">
          <Button label="Clear" @click="reset" />
          <Button
            variant="solid"
            :label="`Create ${rows.length} bank transactions`"
            :loading="importing"
            :disabled="!bankAccount || (activeSection && !activeSection.balanced && !importAnyway)"
            @click="runImport"
          />
        </div>
      </div>
    </div>

    <!-- What is left to reconcile -->
    <div v-if="summary.transactions" class="rounded-xl border border-outline-gray-1 bg-surface-white p-4">
      <div class="text-sm font-semibold text-ink-gray-8">On this account</div>
      <div class="mt-2 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <div><div class="text-xs text-ink-gray-5">Transactions</div><div class="text-ink-gray-8">{{ summary.transactions }}</div></div>
        <div><div class="text-xs text-ink-gray-5">Unreconciled</div><div class="text-ink-gray-8">{{ summary.unreconciled }}</div></div>
        <div><div class="text-xs text-ink-gray-5">Unallocated</div><div class="tabular-nums text-ink-gray-8">{{ money(summary.unallocated) }}</div></div>
        <div class="flex items-end">
          <Button label="Reconcile in ERPNext" @click="openReconcile" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { Button, FormControl, ErrorMessage, FileUploader, call } from 'frappe-ui'
import ComboField from '@/components/ComboField.vue'
import StatCard from '@/components/StatCard.vue'
import { formatMoney } from '@/utils/money.js'

const accountOptions = ref([])
const bankAccount = ref('')
const fileName = ref('')
const fileUrl = ref('')
const rows = ref([])
const sections = ref([])
const sectionIndex = ref(0)
const sample = ref([])

const activeSection = computed(() => sections.value[sectionIndex.value] || null)

function pickSection(i) {
  sectionIndex.value = i
  rows.value = sections.value[i]?.rows || []
}
const parsing = ref(false)
const parseError = ref('')
const error = ref('')
const importing = ref(false)
const submitOnImport = ref(true)
const importAnyway = ref(false)
const result = ref(null)
const summary = reactive({ transactions: 0, unreconciled: 0, unallocated: 0 })

const totals = computed(() => ({
  deposits: rows.value.reduce((sum, r) => sum + Number(r.deposit || 0), 0),
  withdrawals: rows.value.reduce((sum, r) => sum + Number(r.withdrawal || 0), 0),
}))

function money(v) {
  return formatMoney(v || 0)
}

async function loadAccounts() {
  try {
    accountOptions.value = (await call('kamil.bank_statement.list_bank_accounts')) || []
    if (!bankAccount.value && accountOptions.value.length === 1) bankAccount.value = accountOptions.value[0].value
  } catch (e) {
    accountOptions.value = []
  }
}
loadAccounts()

async function onUploaded(file) {
  fileName.value = file?.file_name || ''
  fileUrl.value = file?.file_url || ''
  await parse()
}

async function parse() {
  if (!fileUrl.value) return
  parsing.value = true
  parseError.value = ''
  error.value = ''
  result.value = null
  try {
    const res = await call('kamil.bank_statement.parse_statement', { file_url: fileUrl.value })
    sections.value = res?.sections || []
    sectionIndex.value = 0
    rows.value = res?.rows || []
    sample.value = res?.sample || []
    parseError.value = res?.error || (rows.value.length ? '' : 'No transaction rows were found in this file.')
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not read that file.'
    rows.value = []
  } finally {
    parsing.value = false
  }
}

async function runImport() {
  importing.value = true
  result.value = null
  try {
    const out = await call('kamil.bank_statement.import_rows', {
      bank_account: bankAccount.value,
      rows: JSON.stringify(rows.value),
      submit: submitOnImport.value ? 1 : 0,
    })
    const lines = []
    if (out.skipped?.length) lines.push(`${out.skipped.length} were already on file and were left alone.`)
    if (out.failed?.length) lines.push(...out.failed.slice(0, 5).map((f) => `${f.date}: ${f.error}`))
    result.value = { ok: !out.failed?.length, title: out.summary, lines }
    loadSummary()
  } catch (e) {
    result.value = {
      ok: false,
      title: 'Could not import this statement.',
      lines: [e?.messages?.join(', ') || e?.message || 'Unknown error.'],
    }
  } finally {
    importing.value = false
  }
}

async function loadSummary() {
  if (!bankAccount.value) return
  try {
    Object.assign(summary, (await call('kamil.bank_statement.get_reconciliation_summary', {
      bank_account: bankAccount.value,
    })) || {})
  } catch (e) {
    /* the summary is a nicety, not the point of the page */
  }
}
watch(bankAccount, loadSummary)

function reset() {
  rows.value = []
  sections.value = []
  sectionIndex.value = 0
  sample.value = []
  fileName.value = ''
  fileUrl.value = ''
  result.value = null
  parseError.value = ''
}

// Matching a transaction to an invoice is ERPNext's own tool, which knows about
// payment entries, journal entries and partial allocations.
function openReconcile() {
  window.location.href = '/app/bank-reconciliation-tool'
}
</script>
