<template>
  <div class="space-y-2">
    <div class="text-xs font-medium text-ink-gray-5">{{ title || 'Items' }}</div>
    <div
      v-for="(row, i) in rows"
      :key="i"
      class="flex flex-col gap-2 rounded-md border border-outline-gray-1 p-2 md:flex-row md:items-end"
    >
      <div v-for="col in columns" :key="col.fieldname" class="w-full min-w-0 md:w-auto" :style="{ flex: col.flex || 1 }">
        <LinkField
          v-if="col.fieldtype === 'link'"
          :doctype="col.options"
          :filters="col.filters || {}"
          :placeholder="col.label"
          :modelValue="row[col.fieldname] || ''"
          @update:modelValue="(v) => set(i, col.fieldname, v)"
        />
        <ComboField
          v-else-if="col.fieldtype === 'select'"
          :options="col.selectOptions"
          :placeholder="col.label"
          :modelValue="row[col.fieldname]"
          @update:modelValue="(v) => set(i, col.fieldname, v)"
        />
        <FormControl
          v-else
          :type="col.fieldtype === 'float' || col.fieldtype === 'currency' ? 'number' : 'text'"
          :placeholder="col.label"
          :modelValue="row[col.fieldname]"
          @update:modelValue="(v) => set(i, col.fieldname, v)"
        />
      </div>
      <Button variant="ghost" @click="remove(i)">
        <template #icon><Trash class="h-4 w-4 text-ink-gray-6" /></template>
      </Button>
    </div>
    <Button variant="subtle" label="Add row" @click="add">
      <template #prefix><Plus class="h-4 w-4" /></template>
    </Button>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { Button, FormControl, call } from 'frappe-ui'
import LinkField from '@/components/LinkField.vue'
import ComboField from '@/components/ComboField.vue'
import Plus from '~icons/lucide/plus'
import Trash from '~icons/lucide/trash-2'

const props = defineProps({
  title: String,
  columns: { type: Array, required: true },
  modelValue: { type: Array, default: () => [] },
  // context used to look up the right price for a picked item
  doctype: { type: String, default: '' },
  party: { type: String, default: '' },
  company: { type: String, default: '' },
})

const rateCol = computed(() => props.columns.find((c) => c.fieldtype === 'currency'))

async function fetchRate(i, itemCode) {
  if (!props.doctype || !itemCode) return
  try {
    const r = await call('kamil.api.get_item_rate', {
      item_code: itemCode,
      doctype: props.doctype,
      party: props.party || null,
      company: props.company || null,
    })
    const row = rows.value[i]
    // the user may have changed the row while we were fetching
    if (!row || row.item_code !== itemCode) return
    if (rateCol.value && !row[rateCol.value.fieldname]) row[rateCol.value.fieldname] = r?.rate || 0
    if (!row.qty) row.qty = 1
    sync()
  } catch (e) {
    /* leave the rate for manual entry */
  }
}
const emit = defineEmits(['update:modelValue'])

const rows = ref(props.modelValue.length ? [...props.modelValue] : [{}])

function sync() {
  emit('update:modelValue', rows.value)
}
function set(i, field, val) {
  rows.value[i][field] = val
  sync()
  if (field === 'item_code' && val) fetchRate(i, val)
}
function add() {
  rows.value.push({})
  sync()
}
function remove(i) {
  rows.value.splice(i, 1)
  if (!rows.value.length) rows.value.push({})
  sync()
}
watch(rows, sync, { deep: true })
</script>
