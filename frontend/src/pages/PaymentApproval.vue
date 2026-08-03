<template>
  <div class="mx-auto w-full min-h-0 max-w-2xl flex-1 overflow-auto p-3 md:p-5">
    <div v-if="loading" class="space-y-3">
      <Skeleton v-for="n in 6" :key="n" class="h-10 w-full" />
    </div>

    <div v-else-if="error" class="rounded-lg border border-red-200 bg-red-50 p-6 text-center text-sm text-red-700">
      {{ error }}
    </div>

    <div v-else-if="pr" class="space-y-4">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="min-w-0">
          <h2 class="truncate text-lg font-semibold text-ink-gray-8">{{ pr.name }}</h2>
          <p class="text-sm text-ink-gray-5">{{ isTransfer ? 'Internal transfer approval' : 'Payment approval' }}</p>
        </div>
        <Badge :theme="statusTheme(pr.status)" :label="pr.status || 'Draft'" />
      </div>

      <!-- The figures being approved -->
      <div class="rounded-xl border border-outline-gray-1 bg-surface-white p-4">
        <div class="text-xs uppercase tracking-wide text-ink-gray-4">Amount requested</div>
        <div class="mt-1 text-2xl font-semibold tabular-nums text-ink-gray-9">
          {{ money(isTransfer ? pr.paid_amount : pr.grand_total, pr.currency) }}
        </div>
        <div v-if="isTransfer" class="mt-3 grid grid-cols-2 gap-x-4 gap-y-3 border-t border-outline-gray-1 pt-3 text-sm">
          <div>
            <div class="text-xs text-ink-gray-5">From account</div>
            <div class="truncate text-ink-gray-8">{{ pr.paid_from }}</div>
          </div>
          <div>
            <div class="text-xs text-ink-gray-5">To account</div>
            <div class="truncate text-ink-gray-8">{{ pr.paid_to }}</div>
          </div>
          <div v-if="pr.reference_no">
            <div class="text-xs text-ink-gray-5">Reference no.</div>
            <div class="truncate text-ink-gray-8">{{ pr.reference_no }}</div>
          </div>
          <div v-if="pr.remarks">
            <div class="text-xs text-ink-gray-5">For</div>
            <div class="truncate text-ink-gray-8">{{ pr.remarks }}</div>
          </div>
        </div>
        <div v-else class="mt-3 grid grid-cols-2 gap-x-4 gap-y-3 border-t border-outline-gray-1 pt-3 text-sm">
          <div>
            <div class="text-xs text-ink-gray-5">{{ pr.party_type || 'Party' }}</div>
            <div class="text-ink-gray-8">{{ pr.party_name || pr.party || '—' }}</div>
          </div>
          <div>
            <div class="text-xs text-ink-gray-5">Against</div>
            <div class="truncate text-ink-gray-8">{{ pr.reference_name || '—' }}</div>
          </div>
          <div v-if="pr.outstanding_amount !== null">
            <div class="text-xs text-ink-gray-5">Still outstanding</div>
            <div class="tabular-nums text-ink-gray-8">{{ money(pr.outstanding_amount, pr.currency) }}</div>
          </div>
          <div v-if="pr.is_expense">
            <div class="text-xs text-ink-gray-5">Expense account</div>
            <div class="truncate text-ink-gray-8">{{ pr.expense_account || '—' }}</div>
          </div>
        </div>
      </div>

      <div v-if="pr.attachments?.length || pr.reference_name" class="rounded-xl border border-outline-gray-1 bg-surface-white p-4">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div class="text-xs uppercase tracking-wide text-ink-gray-4">What this is for</div>
          <Button
            v-if="!pr.attachments?.length"
            :loading="fetchingPrint"
            label="Attach the invoice"
            @click="fetchPrint"
          />
        </div>
        <div v-if="printError" class="mt-2 text-xs text-red-600">{{ printError }}</div>
        <div class="mt-2 flex flex-wrap gap-2">
          <a
            v-for="a in pr.attachments"
            :key="a.file_url"
            :href="a.file_url"
            target="_blank"
            rel="noopener"
            class="flex items-center gap-1 rounded-lg border border-outline-gray-2 bg-surface-gray-1 px-2 py-1 text-xs text-ink-blue-3 hover:underline"
          >
            {{ a.file_name }}
          </a>
        </div>
      </div>

      <div v-if="pr.message" class="rounded-lg border border-outline-gray-1 bg-surface-gray-1 p-3 text-sm text-ink-gray-7">
        {{ pr.message }}
      </div>

      <!-- Already decided -->
      <div v-if="isTransfer && pr.docstatus === 1" class="rounded-lg border border-green-200 bg-green-50 p-3 text-sm">
        <div class="font-medium text-green-700">Already paid</div>
        <div class="text-ink-gray-7">The transfer has been released — payment entry {{ pr.name }}.</div>
      </div>
      <div v-if="pr.approved_by" class="rounded-lg border border-green-200 bg-green-50 p-3 text-sm">
        <div class="font-medium text-green-700">Already approved</div>
        <div class="text-ink-gray-7">by {{ pr.approved_by }}<span v-if="pr.approved_on"> · {{ pr.approved_on }}</span></div>
        <div v-if="pr.payment_entries.length" class="mt-1 text-ink-gray-7">
          Payment entry: {{ pr.payment_entries.join(', ') }}
        </div>
      </div>
      <div v-if="pr.rejection_reason" class="rounded-lg border border-red-200 bg-red-50 p-3 text-sm">
        <div class="font-medium text-red-700">Rejected</div>
        <div class="text-ink-gray-7">{{ pr.rejection_reason }}</div>
      </div>

      <!-- Outcome of this session's action -->
      <div v-if="outcome" class="rounded-lg border p-3 text-sm" :class="outcome.ok ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'">
        <div :class="outcome.ok ? 'font-medium text-green-700' : 'font-medium text-red-700'">{{ outcome.title }}</div>
        <div v-for="line in outcome.lines" :key="line" class="text-ink-gray-7">{{ line }}</div>
      </div>

      <!-- The receipt, once there is a payment entry to show -->
      <div v-if="receiptName" class="space-y-3 rounded-xl border border-outline-gray-1 bg-surface-white p-4">
        <div class="flex flex-wrap items-center gap-2 text-sm font-semibold text-ink-gray-8">
          <Receipt class="h-4 w-4 text-ink-gray-6" /> Payment receipt
          <Badge theme="green" :label="receiptName" />
        </div>
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <ComboField
            label="Print format"
            :options="printFormats"
            :modelValue="printFormat"
            @update:modelValue="(v) => (printFormat = v || 'Standard')"
          />
          <FormControl type="text" label="Send to (WhatsApp)" placeholder="+2547…" v-model="receiptPhone" />
        </div>
        <div v-if="receiptResult" class="text-sm" :class="receiptOk ? 'text-green-600' : 'text-red-600'">
          {{ receiptResult }}
        </div>
        <div class="flex flex-wrap justify-end gap-2">
          <Button label="Download PDF" @click="downloadReceipt">
            <template #prefix><Download class="h-4 w-4" /></template>
          </Button>
          <Button variant="solid" :loading="sendingReceipt" label="Send via WhatsApp" @click="sendReceipt">
            <template #prefix><MessageCircle class="h-4 w-4 text-green-600" /></template>
          </Button>
        </div>
      </div>

      <!-- Actions -->
      <div v-if="!pr.can_approve" class="rounded-lg border border-outline-gray-1 bg-surface-gray-1 p-3 text-sm text-ink-gray-6">
        You can view this request but you do not have permission to approve payments.
      </div>
      <template v-else-if="actionable">
        <div class="space-y-3 rounded-xl border border-outline-gray-1 bg-surface-white p-4">
          <ComboField
            label="Mode of Payment"
            :options="modeOptions"
            create-doctype="Mode of Payment"
            :modelValue="mode"
            @update:modelValue="(v) => (mode = v || '')"
            @created="loadModes"
          />
          <div v-if="pr.payment_currency" class="rounded-lg border border-outline-gray-1 bg-surface-gray-1 p-2 text-xs text-ink-gray-7">
            Requested to be paid in <span class="font-medium">{{ pr.payment_currency }}</span>
            <span v-if="pr.exchange_rate">
              at <span class="font-medium">{{ pr.exchange_rate }}</span>
              per {{ pr.currency }} — about
              <span class="font-medium tabular-nums">
                {{ money(pr.grand_total * pr.exchange_rate, pr.payment_currency) }}
              </span>
            </span>
          </div>
          <div v-if="pr.payment_account" class="text-xs" :class="payCurrencyMismatch ? 'text-amber-700' : 'text-ink-gray-5'">
            Paying from <span class="font-medium">{{ pr.payment_account }}</span>
            <span v-if="pr.payment_account_currency"> in <span class="font-medium">{{ pr.payment_account_currency }}</span></span>
            <span v-if="payCurrencyMismatch"> — this request is in {{ pr.currency }}, so the bank will convert.</span>
          </div>
          <p class="text-xs text-ink-gray-5">
            {{
              isTransfer
                ? 'Approving releases the drafted transfer — this is the point at which the money moves.'
                : `Approving creates the payment entry and allocates it against ${pr.reference_name || 'the invoice'} in one step.`
            }}
          </p>
          <div class="flex flex-wrap justify-end gap-2">
            <Button label="Reject" theme="red" @click="rejectOpen = !rejectOpen" />
            <Button
              variant="solid"
              :label="isTransfer ? 'Approve & transfer' : 'Approve & pay'"
              :loading="approving"
              @click="approve"
            />
          </div>
        </div>

        <div v-if="rejectOpen" class="space-y-3 rounded-xl border border-red-200 bg-red-50 p-4">
          <FormControl
            type="textarea"
            :label="isTransfer ? 'Why are you rejecting this transfer?' : 'Why are you rejecting this payment?'"
            placeholder="e.g. Amount does not match the delivery note"
            v-model="rejectReason"
          />
          <div class="flex justify-end gap-2">
            <Button label="Cancel" @click="rejectOpen = false" />
            <Button
              theme="red"
              variant="solid"
              label="Confirm rejection"
              :loading="rejecting"
              :disabled="!rejectReason.trim()"
              @click="reject"
            />
          </div>
        </div>
      </template>

      <div class="flex flex-wrap gap-2">
        <Button
          :label="isTransfer ? 'All payment entries' : 'All payment requests'"
          @click="router.push(isTransfer ? '/list/payment-entry' : '/list/payment-request')"
        />
        <Button label="Open in ERPNext" @click="openDesk" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button, Badge, FormControl, call } from 'frappe-ui'
import Receipt from '~icons/lucide/receipt'
import Download from '~icons/lucide/download'
import MessageCircle from '~icons/lucide/message-circle'
import Skeleton from '@/components/Skeleton.vue'
import ComboField from '@/components/ComboField.vue'
import { statusTheme } from '@/utils/status.js'
import { defaultCurrency } from '@/utils/money.js'

const route = useRoute()
const router = useRouter()

const pr = ref(null)
const loading = ref(false)
const error = ref('')
const approving = ref(false)
const rejecting = ref(false)
const rejectOpen = ref(false)
const rejectReason = ref('')
const outcome = ref(null)
const mode = ref('')
const modeOptions = ref([])

// The payment entry this request produced — the receipt the payer asks for.
const paidEntry = ref('')
const receiptPhone = ref('')
const receiptResult = ref('')
const receiptOk = ref(false)
const sendingReceipt = ref(false)
const printFormats = ref([{ label: 'Standard', value: 'Standard' }])
const printFormat = ref('Standard')

const payCurrencyMismatch = computed(
  () =>
    !!pr.value?.payment_account_currency &&
    !!pr.value?.currency &&
    pr.value.payment_account_currency !== pr.value.currency,
)

// The print is attached in the background when the request is raised; this is the
// way back if that render failed.
const fetchingPrint = ref(false)
const printError = ref('')

async function fetchPrint() {
  fetchingPrint.value = true
  printError.value = ''
  try {
    const out = await call('kamil.payment_flow.build_reference_print', { name: pr.value.name })
    if (out?.attached) await load()
    else printError.value = out?.error || 'The document could not be rendered just now.'
  } catch (e) {
    printError.value = e?.messages?.join(', ') || e?.message || 'Could not attach the document.'
  } finally {
    fetchingPrint.value = false
  }
}

const receiptName = computed(() => paidEntry.value || pr.value?.payment_entries?.[0] || '')

// An internal transfer arrives as ?type=transfer — it is a drafted Payment Entry
// rather than a Payment Request, so it loads and releases through its own endpoints.
const isTransfer = computed(() => route.query.type === 'transfer')

// Only a submitted, undecided request — or a still-drafted transfer — can be acted on.
const actionable = computed(() => {
  if (!pr.value) return false
  if (isTransfer.value) return pr.value.docstatus === 0
  return (
    pr.value.docstatus === 1 &&
    !pr.value.approved_by &&
    !['Paid', 'Payment Ordered', 'Cancelled'].includes(pr.value.status)
  )
})

async function loadPrintFormats() {
  try {
    printFormats.value = (await call('kamil.api.get_print_formats', { doctype: 'Payment Entry' })) || []
    if (!printFormats.value.length) printFormats.value = [{ label: 'Standard', value: 'Standard' }]
    printFormat.value = printFormats.value[0].value
  } catch (e) {
    printFormats.value = [{ label: 'Standard', value: 'Standard' }]
  }
}

function downloadReceipt() {
  const q = new URLSearchParams({
    doctype: 'Payment Entry',
    name: receiptName.value,
    format: printFormat.value || 'Standard',
    no_letterhead: '0',
  })
  window.open(`/api/method/frappe.utils.print_format.download_pdf?${q.toString()}`, '_blank')
}

async function sendReceipt() {
  sendingReceipt.value = true
  receiptResult.value = ''
  try {
    const out = await call('kamil.api.send_document_whatsapp', {
      doctype: 'Payment Entry',
      name: receiptName.value,
      phone_number: receiptPhone.value || null,
      message: `Payment receipt ${receiptName.value}`,
      print_format: printFormat.value || null,
    })
    receiptOk.value = out?.success !== false
    receiptResult.value = receiptOk.value
      ? `Receipt sent to ${out?.phone_number || receiptPhone.value} ✓`
      : out?.error || 'Could not send the receipt.'
    if (out?.warning) receiptResult.value += ` — ${out.warning}`
  } catch (e) {
    receiptOk.value = false
    receiptResult.value = e?.messages?.join(', ') || e?.message || 'Could not send the receipt.'
  } finally {
    sendingReceipt.value = false
  }
}

async function loadModes() {
  try {
    modeOptions.value = (await call('kamil.api.list_modes_of_payment')) || []
  } catch (e) {
    modeOptions.value = []
  }
}

async function load() {
  loading.value = true
  error.value = ''
  outcome.value = null
  try {
    pr.value = await call(
      isTransfer.value ? 'kamil.payment_flow.get_internal_transfer' : 'kamil.payment_flow.get_payment_request',
      { name: route.params.name },
    )
    mode.value = pr.value?.mode_of_payment || ''
    receiptPhone.value = pr.value?.phone_number || ''
    if (isTransfer.value) paidEntry.value = pr.value?.docstatus === 1 ? pr.value.name : ''
    await loadModes()
    if (receiptName.value) loadPrintFormats()
  } catch (e) {
    error.value =
      e?.messages?.join(', ') ||
      e?.message ||
      (isTransfer.value ? 'Could not load this transfer.' : 'Could not load this payment request.')
    pr.value = null
  } finally {
    loading.value = false
  }
}

watch(() => [route.params.name, route.query.type], load, { immediate: true })

async function approve() {
  approving.value = true
  outcome.value = null
  try {
    if (isTransfer.value) {
      const out = await call('kamil.payment_flow.approve_internal_transfer', {
        name: pr.value.name,
        mode_of_payment: mode.value || null,
      })
      paidEntry.value = out.payment_entry || pr.value.name
      loadPrintFormats()
      outcome.value = {
        ok: true,
        title: 'Transfer released.',
        lines: [
          `${money(out.paid_amount, pr.value.currency)} moved from ${pr.value.paid_from} to ${pr.value.paid_to}.`,
        ],
      }
      await load()
      return
    }
    const out = await call('kamil.payment_flow.approve_payment_request', {
      name: pr.value.name,
      mode_of_payment: mode.value || null,
    })
    const lines = [`Payment entry ${out.payment_entry} created for ${money(out.paid_amount, pr.value.currency)}.`]
    lines.push(
      out.reconciled
        ? `Reconciled ${money(out.allocated_amount, pr.value.currency)} against ${pr.value.reference_name}.`
        : 'The entry was created but nothing was allocated — check it in ERPNext.',
    )
    paidEntry.value = out.payment_entry || ''
    loadPrintFormats()
    outcome.value = { ok: true, title: 'Approved.', lines }
    await load()
  } catch (e) {
    outcome.value = {
      ok: false,
      title: 'Could not approve this payment.',
      lines: [e?.messages?.join(', ') || e?.message || 'Unknown error.'],
    }
  } finally {
    approving.value = false
  }
}

async function reject() {
  rejecting.value = true
  try {
    await call(
      isTransfer.value
        ? 'kamil.payment_flow.reject_internal_transfer'
        : 'kamil.payment_flow.reject_payment_request',
      { name: pr.value.name, reason: rejectReason.value.trim() },
    )
    rejectOpen.value = false
    outcome.value = {
      ok: true,
      title: 'Rejected.',
      lines: [
        isTransfer.value
          ? 'The drafted transfer was discarded — nothing moved.'
          : 'The request was cancelled and cannot be paid.',
      ],
    }
    if (isTransfer.value) pr.value = null
    else await load()
  } catch (e) {
    outcome.value = {
      ok: false,
      title: 'Could not reject this payment.',
      lines: [e?.messages?.join(', ') || e?.message || 'Unknown error.'],
    }
  } finally {
    rejecting.value = false
  }
}

function openDesk() {
  const slug = isTransfer.value ? 'payment-entry' : 'payment-request'
  window.location.href = `/app/${slug}/${encodeURIComponent(pr.value.name)}`
}

function money(v, currency) {
  if (v === null || v === undefined) return ''
  try {
    return new Intl.NumberFormat('en-KE', { style: 'currency', currency: currency || defaultCurrency(), maximumFractionDigits: 2 }).format(v)
  } catch {
    return v
  }
}
</script>
