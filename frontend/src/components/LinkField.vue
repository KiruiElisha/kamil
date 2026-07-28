<template>
  <div>
    <label v-if="label" class="mb-1 block text-xs text-ink-gray-5">{{ label }}</label>
    <Combobox
      :options="comboOptions"
      :modelValue="modelValue"
      :placeholder="placeholder || 'Search ' + doctype"
      @update:modelValue="(v) => emit('update:modelValue', v || '')"
      @update:query="onQuery"
    />
    <QuickEntryDialog
      v-if="createOpen"
      v-model="createOpen"
      :doctype="doctype"
      :seed="query"
      @created="onCreated"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Combobox, call, debounce } from 'frappe-ui'
import QuickEntryDialog from '@/components/dialogs/QuickEntryDialog.vue'
import { getQuickEntry } from '@/data/quickEntry.js'

const props = defineProps({
  doctype: { type: String, required: true },
  label: String,
  placeholder: String,
  filters: { type: Object, default: () => ({}) },
  modelValue: { type: String, default: '' },
  // Off inside a quick entry, so dropdowns cannot open dialogs without end.
  allowCreate: { type: Boolean, default: true },
})
const emit = defineEmits(['update:modelValue', 'created'])

const options = ref([])
const query = ref('')
const canCreate = ref(false)
const createOpen = ref(false)

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
  query.value = q || ''
  search(q)
}

// "Create new …" sits at the bottom of the list, exactly like the desk's link fields.
// It only appears when the server says this user may create the doctype.
const comboOptions = computed(() => {
  if (!props.allowCreate || !canCreate.value) return options.value
  const typed = query.value.trim()
  return [
    ...options.value,
    {
      type: 'custom',
      key: `create-${props.doctype}`,
      label: typed ? `+ Create new ${props.doctype}: “${typed}”` : `+ Create new ${props.doctype}`,
      // Always offered: a search that matches nothing is exactly when it is wanted.
      condition: () => true,
      onClick: () => (createOpen.value = true),
    },
  ]
})

async function onCreated({ name }) {
  if (!name) return
  emit('update:modelValue', name)
  emit('created', name)
  await run('') // the new record should be in the list behind the field too
}

onMounted(async () => {
  run('')
  if (props.allowCreate) {
    const meta = await getQuickEntry(props.doctype)
    canCreate.value = !!meta?.can_create
  }
})
</script>
