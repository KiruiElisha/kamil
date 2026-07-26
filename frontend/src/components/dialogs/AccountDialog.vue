<template>
  <Dialog v-model="show" :options="{ title: isEdit ? `Edit ${account.account_name}` : 'New Account', size: 'lg' }">
    <template #body-content>
      <div class="space-y-3">
        <FormControl type="text" label="Account Name" v-model="form.account_name" />
        <FormControl type="text" label="Account Number (optional)" v-model="form.account_number" />

        <ComboField
          label="Parent Account"
          :options="parentOptions"
          :modelValue="form.parent_account"
          @update:modelValue="(v) => (form.parent_account = v || '')"
        />

        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <ComboField
            v-if="!isEdit"
            label="Root Type"
            :options="rootTypes"
            :modelValue="form.root_type"
            @update:modelValue="(v) => (form.root_type = v || '')"
          />
          <ComboField
            label="Account Type"
            :options="accountTypes"
            :modelValue="form.account_type"
            @update:modelValue="(v) => (form.account_type = v || '')"
          />
        </div>

        <div class="flex flex-wrap gap-4">
          <FormControl v-if="!isEdit" type="checkbox" label="Is a group" v-model="form.is_group" />
          <FormControl type="checkbox" label="Disabled" v-model="form.disabled" />
        </div>

        <p v-if="isEdit" class="text-xs text-ink-gray-5">
          Root type and company are fixed once an account exists — changing them would break the tree.
        </p>

        <ErrorMessage :message="error" />
      </div>
    </template>
    <template #actions="{ close }">
      <div class="flex w-full justify-end gap-2">
        <Button label="Cancel" @click="close" />
        <Button variant="solid" :loading="saving" :label="isEdit ? 'Save' : 'Create'" @click="save" />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { Dialog, Button, FormControl, ErrorMessage, call } from 'frappe-ui'
import ComboField from '@/components/ComboField.vue'

const show = defineModel()
const props = defineProps({
  account: { type: Object, default: null },
  parentDefault: { type: String, default: '' },
})
const emit = defineEmits(['saved'])

const isEdit = computed(() => !!props.account?.name)
const saving = ref(false)
const error = ref('')
const parentOptions = ref([])

const rootTypes = ['Asset', 'Liability', 'Equity', 'Income', 'Expense'].map((v) => ({ label: v, value: v }))
const accountTypes = [
  '', 'Accumulated Depreciation', 'Asset Received But Not Billed', 'Bank', 'Cash', 'Chargeable',
  'Capital Work in Progress', 'Cost of Goods Sold', 'Current Asset', 'Current Liability', 'Depreciation',
  'Direct Expense', 'Direct Income', 'Equity', 'Expense Account', 'Expenses Included In Valuation',
  'Fixed Asset', 'Income Account', 'Indirect Expense', 'Indirect Income', 'Payable', 'Receivable',
  'Round Off', 'Stock', 'Stock Adjustment', 'Stock Received But Not Billed', 'Tax', 'Temporary',
].map((v) => ({ label: v || '— none —', value: v }))

const form = reactive({
  account_name: '',
  account_number: '',
  parent_account: '',
  root_type: '',
  account_type: '',
  is_group: false,
  disabled: false,
})

async function loadParents() {
  try {
    parentOptions.value = (await call('kamil.masters.get_account_parents')) || []
  } catch (e) {
    parentOptions.value = []
  }
}

watch(show, (v) => {
  if (!v) return
  error.value = ''
  loadParents()
  const a = props.account
  Object.assign(form, {
    account_name: a?.account_name || '',
    account_number: a?.account_number || '',
    parent_account: a?.parent_account || props.parentDefault || '',
    root_type: a?.root_type || '',
    account_type: a?.account_type || '',
    is_group: !!a?.is_group,
    disabled: !!a?.disabled,
  })
})

async function save() {
  error.value = ''
  if (!form.account_name.trim()) {
    error.value = 'Account name is required.'
    return
  }
  if (!isEdit.value && !form.parent_account) {
    error.value = 'Pick a parent account.'
    return
  }

  saving.value = true
  try {
    const values = {
      account_name: form.account_name.trim(),
      account_number: form.account_number.trim() || null,
      parent_account: form.parent_account,
      account_type: form.account_type || null,
      disabled: form.disabled ? 1 : 0,
    }
    if (isEdit.value) values.name = props.account.name
    else {
      values.root_type = form.root_type || null
      values.is_group = form.is_group ? 1 : 0
    }

    await call('kamil.masters.save_account', { values: JSON.stringify(values) })
    show.value = false
    emit('saved')
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not save the account.'
  } finally {
    saving.value = false
  }
}
</script>
