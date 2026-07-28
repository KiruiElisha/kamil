<template>
  <Dialog v-model="show" :options="{ title: 'Create Invoice from Order', size: 'lg' }">
    <template #body-content>
      <div class="space-y-4">
        <ComboField label="Order type" :options="typeOptions" :modelValue="orderType" @update:modelValue="onType" />
        <div>
          <label class="mb-1 block text-xs text-ink-gray-5">Order</label>
          <Combobox
            :options="orderOptions"
            :modelValue="orderName"
            placeholder="Search un-billed orders"
            @update:modelValue="(v) => (orderName = v || '')"
          />
        </div>
        <p class="text-sm text-ink-gray-5">A draft invoice will be created from the selected order.</p>
        <ErrorMessage :message="error" />
      </div>
    </template>
    <template #actions="{ close }">
      <div class="flex justify-end gap-2">
        <Button label="Cancel" @click="close" />
        <Button variant="solid" label="Create draft invoice" :loading="loading" @click="create" />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Dialog, Button, ErrorMessage, Combobox, call } from 'frappe-ui'
import ComboField from '@/components/ComboField.vue'

const show = defineModel()
const emit = defineEmits(['created'])

const typeOptions = [
  { label: 'Sales Order → Sales Invoice', value: 'Sales' },
  { label: 'Purchase Order → Purchase Invoice', value: 'Purchase' },
]

const orderType = ref('Sales')
const orderName = ref('')
const error = ref('')
const loading = ref(false)
const orderOptions = ref([])

function onType(v) {
  orderType.value = v
  loadOrders()
}
async function loadOrders() {
  orderName.value = ''
  try {
    orderOptions.value = (await call('kamil.api.list_open_orders', { order_type: orderType.value })) || []
  } catch {
    orderOptions.value = []
  }
}
watch(show, (v) => {
  if (v) {
    error.value = ''
    loadOrders()
  }
})

async function create() {
  error.value = ''
  if (!orderName.value) {
    error.value = 'Please select an order.'
    return
  }
  loading.value = true
  try {
    const out = await call('kamil.api.make_invoice_from_order', { order_type: orderType.value, order_name: orderName.value })
    show.value = false
    emit('created', out)
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not create invoice.'
  } finally {
    loading.value = false
  }
}
</script>
