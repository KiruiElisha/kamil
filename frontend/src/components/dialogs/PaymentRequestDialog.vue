<template>
  <Dialog v-model="show" :options="{ title: 'Request a Payment', size: '2xl' }">
    <template #body-content>
      <div class="space-y-4">
        <Tabs v-model="tab" :tabs="tabs" />

        <!-- Against an existing invoice -->
        <div v-if="tab === 0" class="space-y-3">
          <ComboField
            label="Supplier invoice"
            placeholder="Pick an invoice with something outstanding (newest first)"
            :options="payableOptions"
            :modelValue="form.reference_name"
            @update:modelValue="onInvoiceChange"
          />
          <div v-if="selectedPayable" class="rounded-lg border border-outline-gray-1 bg-surface-gray-1 px-3 py-2 text-sm">
            <span class="text-ink-gray-5">Outstanding:</span>
            <span class="font-medium text-ink-gray-8">
              {{ money(selectedPayable.outstanding, selectedPayable.currency) }}
            </span>
          </div>
          <FormControl type="number" label="Amount to request" v-model="form.amount" />
        </div>

        <!-- Between the company's own accounts -->
        <div v-else-if="tab === 2" class="space-y-3">
          <p class="rounded-lg bg-surface-gray-1 px-3 py-2 text-xs text-ink-gray-6">
            Moves money between your own accounts — bank to cash, one bank to another. It is
            drafted as an Internal Transfer payment entry and nothing moves until it is approved.
          </p>
          <LinkField
            label="From account"
            doctype="Account"
            :filters="{ is_group: 0, account_type: ['in', ['Bank', 'Cash']] }"
            :modelValue="form.paid_from"
            @update:modelValue="(v) => (form.paid_from = v)"
          />
          <LinkField
            label="To account"
            doctype="Account"
            :filters="{ is_group: 0, account_type: ['in', ['Bank', 'Cash']] }"
            :modelValue="form.paid_to"
            @update:modelValue="(v) => (form.paid_to = v)"
          />
          <FormControl type="number" label="Amount" v-model="form.amount" />
          <FormControl type="text" label="Reference no. (optional)" placeholder="e.g. cheque or slip number" v-model="form.reference_no" />
          <FormControl type="text" label="What is this for?" placeholder="e.g. Float for the Nakuru depot" v-model="form.description" />
        </div>

        <!-- A direct expense -->
        <div v-else class="space-y-3">
          <p class="rounded-lg bg-surface-gray-1 px-3 py-2 text-xs text-ink-gray-6">
            An expense books a Purchase Invoice against the account you pick, then raises the
            payment request for it. Approving pays and reconciles that invoice.
          </p>
          <LinkField
            label="Supplier / Payee"
            doctype="Supplier"
            :filters="{ disabled: 0 }"
            :modelValue="form.supplier"
            @update:modelValue="(v) => (form.supplier = v)"
          />
          <LinkField
            label="Expense Account"
            doctype="Account"
            :filters="{ is_group: 0, root_type: 'Expense' }"
            :modelValue="form.expense_account"
            @update:modelValue="(v) => (form.expense_account = v)"
          />
          <FormControl type="text" label="What is this for?" placeholder="e.g. Generator diesel — March" v-model="form.description" />
          <FormControl type="number" label="Amount" v-model="form.amount" />
          <LinkField label="Cost Center (optional)" doctype="Cost Center" :filters="{ is_group: 0 }" :modelValue="form.cost_center" @update:modelValue="(v) => (form.cost_center = v)" />
        </div>

        <!-- Shared: what will be paid, and who approves it -->
        <div class="grid grid-cols-1 gap-3 border-t border-outline-gray-1 pt-3 sm:grid-cols-2">
          <LinkField
            label="Pay in currency"
            doctype="Currency"
            :modelValue="form.payment_currency"
            @update:modelValue="onPaymentCurrency"
          />
          <FormControl
            v-if="needsRate"
            type="number"
            :label="`Exchange rate (1 ${requestCurrency} = ? ${form.payment_currency})`"
            v-model="form.exchange_rate"
          />
          <div v-if="needsRate" class="text-xs text-ink-gray-5 sm:col-span-2">
            {{ rateHint }}
          </div>
          <ComboField
            label="Approver"
            :options="approverOptions"
            :modelValue="form.recipient"
            :placeholder="approverOptions.length ? 'Pick who approves this' : 'No approvers found'"
            @update:modelValue="(v) => (form.recipient = v || '')"
          />
          <FormControl type="text" label="Approver WhatsApp (optional)" placeholder="+2547…" v-model="form.phone_number" />
          <div class="flex items-end gap-4">
            <FormControl type="checkbox" label="Send email" v-model="form.via_email" />
            <FormControl type="checkbox" label="Send WhatsApp" v-model="form.via_whatsapp" />
          </div>
        </div>

        <div v-if="result" class="space-y-1 rounded-lg border p-3 text-sm" :class="result.ok ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'">
          <div :class="result.ok ? 'font-medium text-green-700' : 'font-medium text-red-700'">{{ result.title }}</div>
          <div v-for="line in result.lines" :key="line" class="text-ink-gray-7">{{ line }}</div>
        </div>

        <ErrorMessage :message="error" />
      </div>
    </template>
    <template #actions="{ close }">
      <div class="flex w-full justify-end gap-2">
        <Button label="Close" @click="close" />
        <Button variant="solid" :loading="saving" :label="submitLabel" @click="submit" />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { Dialog, Button, FormControl, ErrorMessage, Tabs, call } from 'frappe-ui'
import ComboField from '@/components/ComboField.vue'
import LinkField from '@/components/LinkField.vue'
import { defaultCurrency } from '@/utils/money.js'

const show = defineModel()
const emit = defineEmits(['created'])

const tabs = [{ label: 'Against invoice' }, { label: 'Direct expense' }, { label: 'Internal transfer' }]
const tab = ref(0)

// A payment request is how the company asks to pay someone. Money coming in from a
// customer is recorded against the sales invoice instead, so there is nothing to pick.
const refType = ref('Purchase Invoice')

const saving = ref(false)
const error = ref('')
const result = ref(null)

const payableOptions = ref([])
// Only users who hold an approving role — sending it to anyone else just produces a
// link they cannot act on.
const approverOptions = ref([])
const payables = ref([])

const form = reactive({
  reference_name: '',
  amount: null,
  supplier: '',
  expense_account: '',
  description: '',
  cost_center: '',
  paid_from: '',
  paid_to: '',
  reference_no: '',
  payment_currency: '',
  exchange_rate: null,
  recipient: '',
  phone_number: '',
  via_email: true,
  via_whatsapp: true,
})

// Which account the money actually leaves, and in what currency — often not the
// currency on the invoice (a USD invoice paid from a KES account).
// The mode of payment — and so which account the money leaves — is the approver's
// call, not the requester's. What the requester states is the currency it will be
// paid in and the rate to use.
const rateSource = ref('')
const needsRate = computed(
  () => !!form.payment_currency && !!requestCurrency.value && form.payment_currency !== requestCurrency.value,
)
const rateHint = computed(() =>
  rateSource.value === 'Currency Exchange'
    ? `Suggested from the latest Currency Exchange record — change it if the bank used another rate.`
    : `No rate on file for ${requestCurrency.value} to ${form.payment_currency} — enter the one the bank will use.`,
)

async function onPaymentCurrency(value) {
  form.payment_currency = value || ''
  rateSource.value = ''
  if (!needsRate.value) {
    form.exchange_rate = null
    return
  }
  try {
    const res = await call('kamil.api.get_exchange_rate', {
      from_currency: requestCurrency.value,
      to_currency: form.payment_currency,
    })
    rateSource.value = res?.source || ''
    if (res?.rate) form.exchange_rate = res.rate
  } catch (e) {
    /* the rate can still be typed in */
  }
}
const requestCurrency = computed(() => selectedPayable.value?.currency || defaultCurrency())
const currencyMismatch = computed(
  () => !!payingFrom.value && !!requestCurrency.value && payingFrom.value.currency !== requestCurrency.value,
)

const selectedPayable = computed(() => payables.value.find((p) => p.value === form.reference_name) || null)

function reset() {
  Object.assign(form, {
    reference_name: '',
    amount: null,
    supplier: '',
    expense_account: '',
    description: '',
    cost_center: '',
    paid_from: '',
    paid_to: '',
    reference_no: '',
    payment_currency: '',
    exchange_rate: null,
    recipient: '',
    phone_number: '',
    via_email: true,
    via_whatsapp: true,
  })
  error.value = ''
  result.value = null
  tab.value = 0
}

async function loadPayables() {
  try {
    const rows = await call('kamil.payment_flow.list_payable_documents', { reference_doctype: refType.value })
    payables.value = rows || []
    payableOptions.value = payables.value.map((r) => ({ label: r.label, value: r.value }))
  } catch (e) {
    payables.value = []
    payableOptions.value = []
  }
}

async function loadApprovers() {
  try {
    approverOptions.value = (await call('kamil.payment_flow.list_payment_approvers')) || []
    // One approver is not a choice; pre-select it.
    if (!form.recipient && approverOptions.value.length === 1) {
      form.recipient = approverOptions.value[0].value
    }
  } catch (e) {
    approverOptions.value = []
  }
}

// One person receives payment requests (Settings -> Payment approvals), so the form
// starts there rather than asking every time.
async function loadApprover() {
  try {
    const s = await call('kamil.payment_flow.get_payment_settings')
    if (s?.email && !form.recipient) form.recipient = s.email
    if (s?.phone && !form.phone_number) form.phone_number = s.phone
    if (s?.notify_by_email !== undefined) form.via_email = !!s.notify_by_email
    if (s?.notify_by_whatsapp !== undefined) form.via_whatsapp = !!s.notify_by_whatsapp
  } catch (e) {
    /* the approver can still be typed in */
  }
}

watch(show, (v) => {
  if (!v) return
  reset()
  loadPayables()
  loadApprover()
  loadApprovers()
})


// Default the amount to whatever is still outstanding — the common case.
function onInvoiceChange(v) {
  form.reference_name = v || ''
  const row = payables.value.find((p) => p.value === form.reference_name)
  if (row) form.amount = row.outstanding
}

function money(v, currency) {
  if (v === null || v === undefined) return ''
  try {
    return new Intl.NumberFormat('en-KE', { style: 'currency', currency: currency || defaultCurrency(), maximumFractionDigits: 2 }).format(v)
  } catch {
    return v
  }
}

function describeSend(out) {
  const lines = [`Approval link: ${out.link}`]
  if (out.email) lines.push(out.email.sent ? `Emailed to ${out.email.to}` : `Email not sent — ${out.email.error}`)
  if (out.whatsapp)
    lines.push(out.whatsapp.sent ? `WhatsApp sent to ${out.whatsapp.to}` : `WhatsApp not sent — ${out.whatsapp.error}`)
  return lines
}

const submitLabel = computed(
  () => ['Request payment', 'Book & request', 'Request transfer'][tab.value] || 'Request payment',
)

async function submit() {
  error.value = ''
  result.value = null
  saving.value = true
  try {
    let created
    let isTransfer = false
    if (tab.value === 2) {
      isTransfer = true
      if (!form.paid_from) throw new Error('Pick the account the money comes from.')
      if (!form.paid_to) throw new Error('Pick the account the money goes to.')
      if (!form.amount) throw new Error('Enter the amount.')
      created = await call('kamil.payment_flow.create_internal_transfer', {
        paid_from: form.paid_from,
        paid_to: form.paid_to,
        amount: form.amount,
        reference_no: form.reference_no || null,
        remarks: form.description || null,
      })
    } else if (tab.value === 0) {
      if (!form.reference_name) throw new Error('Pick an invoice to request payment against.')
      created = await call('kamil.payment_flow.create_payment_request', {
        reference_doctype: refType.value,
        reference_name: form.reference_name,
        amount: form.amount || null,
        recipient: form.recipient || null,
        phone_number: form.phone_number || null,
        payment_currency: form.payment_currency || null,
        exchange_rate: form.exchange_rate || null,
      })
    } else {
      if (!form.supplier) throw new Error('Pick the supplier or payee.')
      if (!form.expense_account) throw new Error('Pick the expense account to book this against.')
      if (!form.amount) throw new Error('Enter the amount.')
      created = await call('kamil.payment_flow.create_expense_payment_request', {
        company: null,
        supplier: form.supplier,
        expense_account: form.expense_account,
        amount: form.amount,
        description: form.description || null,
        cost_center: form.cost_center || null,
        recipient: form.recipient || null,
        phone_number: form.phone_number || null,
        payment_currency: form.payment_currency || null,
        exchange_rate: form.exchange_rate || null,
      })
    }

    // Sending is a separate step so a mail failure never loses the request itself.
    let sendOut = null
    if (form.via_email || form.via_whatsapp) {
      sendOut = await call(
        isTransfer ? 'kamil.payment_flow.send_internal_transfer' : 'kamil.payment_flow.send_payment_request',
        {
          name: created.name,
          via_email: form.via_email ? 1 : 0,
          via_whatsapp: form.via_whatsapp ? 1 : 0,
          recipient: form.recipient || null,
          phone_number: form.phone_number || null,
        },
      )
    }

    result.value = {
      ok: true,
      title: `${created.name} raised and awaiting approval.`,
      lines: sendOut
        ? describeSend(sendOut)
        : [
            created.link
              ? `Not sent — approval link: ${created.link}`
              : 'Not sent — share the request manually or send it later.',
          ],
    }
    emit('created')
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not raise the payment request.'
  } finally {
    saving.value = false
  }
}
</script>
