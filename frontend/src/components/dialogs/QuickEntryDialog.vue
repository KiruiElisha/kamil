<template>
  <Dialog v-model="show" :options="{ title: `New ${meta.label || doctype}`, size: 'lg' }">
    <template #body-content>
      <div v-if="loading" class="p-6 text-center text-sm text-ink-gray-5">Loading…</div>
      <div v-else-if="!meta.can_create" class="p-6 text-center text-sm text-ink-gray-5">
        You do not have permission to create {{ meta.label || doctype }} records.
      </div>
      <div v-else class="space-y-4">
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FormControl
            v-if="meta.prompt_name"
            type="text"
            label="Name"
            v-model="values.__newname"
          />
          <template v-for="f in meta.fields" :key="f.fieldname">
            <!-- Link fields inside a quick entry do not offer their own "create new",
                 so a dropdown can never open dialogs without end. -->
            <LinkField
              v-if="f.fieldtype === 'Link'"
              :label="fieldLabel(f)"
              :doctype="f.options"
              :allow-create="false"
              :modelValue="values[f.fieldname] || ''"
              @update:modelValue="(v) => (values[f.fieldname] = v)"
            />
            <ComboField
              v-else-if="f.fieldtype === 'Select'"
              :label="fieldLabel(f)"
              :options="f.select_options"
              :modelValue="values[f.fieldname]"
              @update:modelValue="(v) => (values[f.fieldname] = v || '')"
            />
            <FormControl
              v-else-if="f.fieldtype === 'Check'"
              type="checkbox"
              :label="fieldLabel(f)"
              :modelValue="!!values[f.fieldname]"
              @update:modelValue="(v) => (values[f.fieldname] = v ? 1 : 0)"
            />
            <FormControl
              v-else
              :type="controlType(f.fieldtype)"
              :label="fieldLabel(f)"
              v-model="values[f.fieldname]"
            />
          </template>
        </div>
        <ErrorMessage :message="error" />
      </div>
    </template>
    <template #actions="{ close }">
      <div class="flex justify-end gap-2">
        <Button label="Cancel" @click="close" />
        <Button
          v-if="meta.can_create"
          variant="solid"
          :label="`Create ${meta.label || doctype}`"
          :loading="saving"
          @click="create"
        />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { Dialog, Button, FormControl, ErrorMessage, call } from 'frappe-ui'
import LinkField from '@/components/LinkField.vue'
import ComboField from '@/components/ComboField.vue'
import { getQuickEntry } from '@/data/quickEntry.js'
import { getDefaults } from '@/data/defaults.js'

const show = defineModel()
const props = defineProps({
  doctype: { type: String, required: true },
  // What the user had already typed in the dropdown — seeded into the name field.
  seed: { type: String, default: '' },
})
const emit = defineEmits(['created'])

const meta = ref({ can_create: false, fields: [], label: '' })
const values = reactive({})
const loading = ref(false)
const saving = ref(false)
const error = ref('')

function controlType(fieldtype) {
  if (['Int', 'Float', 'Currency', 'Percent'].includes(fieldtype)) return 'number'
  if (fieldtype === 'Date') return 'date'
  if (fieldtype === 'Datetime') return 'datetime-local'
  if (['Small Text', 'Long Text', 'Text'].includes(fieldtype)) return 'textarea'
  return 'text'
}

function fieldLabel(f) {
  return f.reqd ? `${f.label} *` : f.label
}

function today() {
  return new Date().toISOString().slice(0, 10)
}

/** The field the typed text belongs in: the title field, else the first required text field. */
function seedField(fields) {
  const byTitle = fields.find((f) => f.fieldname === meta.value.title_field)
  if (byTitle) return byTitle
  return fields.find((f) => f.reqd && f.fieldtype === 'Data') || fields.find((f) => f.fieldtype === 'Data')
}

async function load() {
  loading.value = true
  error.value = ''
  Object.keys(values).forEach((k) => delete values[k])
  try {
    meta.value = (await getQuickEntry(props.doctype)) || { can_create: false, fields: [] }
    const defaults = (await getDefaults()) || {}

    for (const f of meta.value.fields || []) {
      let value = f.default || ''
      if (['Today', 'today'].includes(value)) value = today()
      else if (value.startsWith && value.startsWith('__')) value = '' // user/session tokens
      // Company and warehouse are already resolved for the app's create modals.
      if (!value && f.fieldname === 'company') value = defaults.company || ''
      if (!value && f.fieldname === 'warehouse') value = defaults.warehouse || ''
      if (f.fieldtype === 'Check') value = value ? 1 : 0
      values[f.fieldname] = value
    }

    const seedInto = seedField(meta.value.fields || [])
    if (props.seed && seedInto && !values[seedInto.fieldname]) values[seedInto.fieldname] = props.seed
    else if (props.seed && meta.value.prompt_name) values.__newname = props.seed
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not load this form.'
  } finally {
    loading.value = false
  }
}

watch(show, (v) => {
  if (v) load()
})

function clean() {
  const out = {}
  for (const [k, v] of Object.entries(values)) {
    if (v !== '' && v !== null && v !== undefined) out[k] = v
  }
  return out
}

async function create() {
  error.value = ''
  const missing = (meta.value.fields || []).filter((f) => f.reqd && !values[f.fieldname] && f.fieldtype !== 'Check')
  if (missing.length) {
    error.value = `Please fill in: ${missing.map((f) => f.label).join(', ')}`
    return
  }
  if (meta.value.prompt_name && !values.__newname) {
    error.value = 'Please give this record a name.'
    return
  }

  saving.value = true
  try {
    const out = await call('kamil.api.create_document', {
      doctype: props.doctype,
      values: JSON.stringify(clean()),
    })
    emit('created', { name: out?.name, doctype: props.doctype })
    show.value = false
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not create this record.'
  } finally {
    saving.value = false
  }
}
</script>
