<template>
  <div>
    <label v-if="label" class="mb-1 block text-xs text-ink-gray-5">{{ label }}</label>
    <Combobox
      :options="options"
      :modelValue="modelValue"
      :placeholder="placeholder || 'Search ' + doctype"
      @update:modelValue="(v) => emit('update:modelValue', v || '')"
      @update:query="onQuery"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Combobox, call, debounce } from 'frappe-ui'

const props = defineProps({
  doctype: { type: String, required: true },
  label: String,
  placeholder: String,
  filters: { type: Object, default: () => ({}) },
  modelValue: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const options = ref([])

async function run(txt) {
  try {
    const data = await call('kamil.api.search_link', {
      doctype: props.doctype,
      txt: txt || '',
      filters: props.filters || {},
    })
    options.value = (Array.isArray(data) ? data : []).map((o) => ({ label: o.label, value: o.value }))
  } catch (e) {
    options.value = []
  }
}
const search = debounce(run, 200)

function onQuery(q) {
  search(q)
}

onMounted(() => run(''))
</script>
