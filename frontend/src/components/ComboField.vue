<template>
  <div>
    <label v-if="label" class="mb-1 block text-xs text-ink-gray-5">{{ label }}</label>
    <Combobox
      :options="comboOptions"
      :modelValue="modelValue"
      :placeholder="placeholder || 'Select'"
      @update:modelValue="(v) => emit('update:modelValue', v)"
    />
    <QuickEntryDialog
      v-if="createOpen"
      v-model="createOpen"
      :doctype="createDoctype"
      @created="onCreated"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Combobox } from 'frappe-ui'
import QuickEntryDialog from '@/components/dialogs/QuickEntryDialog.vue'
import { getQuickEntry } from '@/data/quickEntry.js'

const props = defineProps({
  options: { type: Array, default: () => [] },
  label: String,
  placeholder: String,
  modelValue: { type: [String, Number], default: '' },
  // Set when the options come from a doctype (Mode of Payment, …) so the dropdown
  // can offer "Create new" the same way a link field does.
  createDoctype: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'created'])

const canCreate = ref(false)
const createOpen = ref(false)

const comboOptions = computed(() => {
  if (!props.createDoctype || !canCreate.value) return props.options
  return [
    ...props.options,
    {
      type: 'custom',
      key: `create-${props.createDoctype}`,
      label: `+ Create new ${props.createDoctype}`,
      // Always offered: a search that matches nothing is exactly when it is wanted.
      condition: () => true,
      onClick: () => (createOpen.value = true),
    },
  ]
})

function onCreated({ name }) {
  if (!name) return
  emit('update:modelValue', name)
  // The parent owns the option list, so it has to refetch to show the new record.
  emit('created', name)
}

onMounted(async () => {
  if (!props.createDoctype) return
  const meta = await getQuickEntry(props.createDoctype)
  canCreate.value = !!meta?.can_create
})
</script>
