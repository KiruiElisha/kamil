<template>
  <Dialog v-model="show" :options="{ title: 'Record Payment', size: 'lg' }">
    <template #body-content>
      <div class="space-y-4">
        <ComboField label="Payment for" :options="typeOptions" :modelValue="invoiceType" @update:modelValue="onType" />
        <div>
          <label class="mb-1 block text-xs text-ink-gray-5">Outstanding invoice</label>
          <Combobox
            :options="invoiceOptions"
            :modelValue="invoiceName"
            placeholder="Search invoices"
            @update:modelValue="(v) => (invoiceName = v || '')"
          />
        </div>
        <div v-if="selectedInvoice" class="rounded-md bg-surface-gray-2 px-3 py-2 text-sm text-ink-gray-7">
          Outstanding:
          <span class="font-medium text-ink-gray-9">{{ money(selectedInvoice.outstanding, selectedInvoice.currency) }}</span>
        </div>
        <FormControl type="number" label="Amount" placeholder="Leave blank for full outstanding" v-model="amount" />
        <ComboField
          label="Mode of payment"
          :options="modeOptions"
          create-doctype="Mode of Payment"
          :modelValue="modeName"
          @update:modelValue="(v) => (modeName = v || '')"
          @created="loadModes"
        />
        <ErrorMessage :message="error" />
      </div>
    </template>
    <template #actions="{ close }">
      <div class="flex justify-end gap-2">
        <Button label="Cancel" @click="close" />
        <Button variant="solid" label="Create draft payment" :loading="loading" @click="create" />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { Dialog, Button, FormControl, ErrorMessage, Combobox, call } from 'frappe-ui'
import ComboField from '@/components/ComboField.vue'

const show = defineModel()
const emit = defineEmits(['created'])

const typeOptions = [
  { label: 'Receive from Customer (Sales Invoice)', value: 'Sales' },
  { label: 'Pay Supplier (Purchase Invoice)', value: 'Purchase' },
]

const invoiceType = ref('Sales')
const invoiceName = ref('')
const amount = ref('')
const modeName = ref('')
const error = ref('')
const loading = ref(false)
const invoiceOptions = ref([])
const modeOptions = ref([])

const selectedInvoice = computed(() => invoiceOptions.value.find((o) => o.value === invoiceName.value))

function onType(v) {
  invoiceType.value = v
  loadInvoices()
}
async function loadInvoices() {
  invoiceName.value = ''
  try {
    invoiceOptions.value = (await call('kamil.api.list_open_invoices', { invoice_type: invoiceType.value })) || []
  } catch {
    invoiceOptions.value = []
  }
}
async function loadModes() {
  try {
    modeOptions.value = (await call('kamil.api.list_modes_of_payment')) || []
  } catch {
    modeOptions.value = []
  }
}
onMounted(loadModes)
watch(show, (v) => {
  if (v) {
    error.value = ''
    loadInvoices()
  }
})

async function create() {
  error.value = ''
  if (!invoiceName.value) {
    error.value = 'Please select an invoice.'
    return
  }
  loading.value = true
  try {
    const out = await call('kamil.api.record_payment', {
      invoice_type: invoiceType.value,
      invoice_name: invoiceName.value,
      amount: amount.value || null,
      mode_of_payment: modeName.value || null,
    })
    show.value = false
    emit('created', out)
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not create payment.'
  } finally {
    loading.value = false
  }
}

function money(v, c) {
  try {
    return new Intl.NumberFormat('en-KE', { style: 'currency', currency: c || 'KES', maximumFractionDigits: 0 }).format(v || 0)
  } catch {
    return v
  }
}
</script>
