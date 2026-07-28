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
import Skeleton from '@/components/Skeleton.vue'
import ComboField from '@/components/ComboField.vue'
import { statusTheme } from '@/utils/status.js'

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
    await loadModes()
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
    return new Intl.NumberFormat('en-KE', { style: 'currency', currency: currency || 'KES', maximumFractionDigits: 2 }).format(v)
  } catch {
    return v
  }
}
</script>
