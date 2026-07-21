<template>
  <div>
    <label v-if="label" class="mb-1 block text-xs text-ink-gray-5">{{ label }}</label>
    <Combobox
      :options="options"
      :modelValue="modelValue"
      :placeholder="placeholder || 'Select'"
      @update:modelValue="(v) => emit('update:modelValue', v)"
    />
  </div>
</template>

<script setup>
import { Combobox } from 'frappe-ui'

defineProps({
  options: { type: Array, default: () => [] },
  label: String,
  placeholder: String,
  modelValue: { type: [String, Number], default: '' },
})
const emit = defineEmits(['update:modelValue'])
</script>
