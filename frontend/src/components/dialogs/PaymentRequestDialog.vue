<template>
  <Dialog v-model="show" :options="{ title: 'Request a Payment', size: '2xl' }">
    <template #body-content>
      <div class="space-y-4">
        <Tabs v-model="tab" :tabs="tabs" />

        <!-- Against an existing invoice -->
        <div v-if="tab === 0" class="space-y-3">
          <ComboField
            label="Pay against"
            :options="refTypeOptions"
            :modelValue="refType"
            @update:modelValue="onRefTypeChange"
          />
          <ComboField
            label="Invoice"
            placeholder="Pick an invoice with something outstanding"
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

        <!-- A direct expense -->
        <div v-else class="space-y-3">
          <p class="rounded-lg bg-surface-gray-1 px-3 py-2 text-xs text-ink-gray-6">
            An expense books a Purchase Invoice against the account you pick, then raises the
            payment request for it. Approving pays and reconciles that invoice.
          </p>
          <LinkField label="Supplier / Payee" doctype="Supplier" :modelValue="form.supplier" @update:modelValue="(v) => (form.supplier = v)" />
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

        <!-- Shared: how it gets paid and who approves -->
        <div class="grid grid-cols-1 gap-3 border-t border-outline-gray-1 pt-3 sm:grid-cols-2">
          <ComboField
            label="Mode of Payment"
            :options="modeOptions"
            create-doctype="Mode of Payment"
            :modelValue="form.mode_of_payment"
            @update:modelValue="(v) => (form.mode_of_payment = v || '')"
            @created="loadModes"
          />
          <FormControl type="text" label="Approver email" placeholder="approver@company.com" v-model="form.recipient" />
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
        <Button variant="solid" :loading="saving" :label="tab === 0 ? 'Request payment' : 'Book & request'" @click="submit" />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { Dialog, Button, FormControl, ErrorMessage, Tabs, call } from 'frappe-ui'
import ComboField from '@/components/ComboField.vue'
import LinkField from '@/components/LinkField.vue'

const show = defineModel()
const emit = defineEmits(['created'])

const tabs = [{ label: 'Against invoice' }, { label: 'Direct expense' }]
const tab = ref(0)

const refTypeOptions = [
  { label: 'Purchase Invoice (we pay)', value: 'Purchase Invoice' },
  { label: 'Sales Invoice (customer pays)', value: 'Sales Invoice' },
]
const refType = ref('Purchase Invoice')

const saving = ref(false)
const error = ref('')
const result = ref(null)

const payableOptions = ref([])
const payables = ref([])
const modeOptions = ref([])

const form = reactive({
  reference_name: '',
  amount: null,
  supplier: '',
  expense_account: '',
  description: '',
  cost_center: '',
  mode_of_payment: '',
  recipient: '',
  phone_number: '',
  via_email: true,
  via_whatsapp: false,
})

const selectedPayable = computed(() => payables.value.find((p) => p.value === form.reference_name) || null)

function reset() {
  Object.assign(form, {
    reference_name: '',
    amount: null,
    supplier: '',
    expense_account: '',
    description: '',
    cost_center: '',
    mode_of_payment: '',
    recipient: '',
    phone_number: '',
    via_email: true,
    via_whatsapp: false,
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

async function loadModes() {
  try {
    modeOptions.value = (await call('kamil.api.list_modes_of_payment')) || []
  } catch (e) {
    modeOptions.value = []
  }
}

watch(show, (v) => {
  if (!v) return
  reset()
  loadPayables()
  loadModes()
})

function onRefTypeChange(v) {
  refType.value = v || 'Purchase Invoice'
  form.reference_name = ''
  form.amount = null
  loadPayables()
}

// Default the amount to whatever is still outstanding — the common case.
function onInvoiceChange(v) {
  form.reference_name = v || ''
  const row = payables.value.find((p) => p.value === form.reference_name)
  if (row) form.amount = row.outstanding
}

function money(v, currency) {
  if (v === null || v === undefined) return ''
  try {
    return new Intl.NumberFormat('en-KE', { style: 'currency', currency: currency || 'KES', maximumFractionDigits: 2 }).format(v)
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

async function submit() {
  error.value = ''
  result.value = null
  saving.value = true
  try {
    let created
    if (tab.value === 0) {
      if (!form.reference_name) throw new Error('Pick an invoice to request payment against.')
      created = await call('kamil.payment_flow.create_payment_request', {
        reference_doctype: refType.value,
        reference_name: form.reference_name,
        amount: form.amount || null,
        mode_of_payment: form.mode_of_payment || null,
        recipient: form.recipient || null,
        phone_number: form.phone_number || null,
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
        mode_of_payment: form.mode_of_payment || null,
        cost_center: form.cost_center || null,
        recipient: form.recipient || null,
        phone_number: form.phone_number || null,
      })
    }

    // Sending is a separate step so a mail failure never loses the request itself.
    let sendOut = null
    if (form.via_email || form.via_whatsapp) {
      sendOut = await call('kamil.payment_flow.send_payment_request', {
        name: created.name,
        via_email: form.via_email ? 1 : 0,
        via_whatsapp: form.via_whatsapp ? 1 : 0,
        recipient: form.recipient || null,
        phone_number: form.phone_number || null,
      })
    }

    result.value = {
      ok: true,
      title: `${created.name} raised and awaiting approval.`,
      lines: sendOut ? describeSend(sendOut) : ['Not sent — share the request manually or send it later.'],
    }
    emit('created')
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not raise the payment request.'
  } finally {
    saving.value = false
  }
}
</script>
