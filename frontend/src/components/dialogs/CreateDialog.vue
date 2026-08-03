<template>
  <Dialog v-model="show" :options="{ title: config?.title || 'New', size: config?.child || config?.children?.length ? '5xl' : 'lg' }">
    <template #body-content>
      <div v-if="config" class="space-y-4">
        <div v-for="(group, gi) in groups" :key="group.title || gi" class="space-y-3">
          <div
            v-if="group.title"
            class="border-b border-outline-gray-1 pb-1 text-xs font-semibold uppercase tracking-wide text-ink-gray-5"
          >
            {{ group.title }}
          </div>
          <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <template v-for="f in group.fields" :key="f.fieldname">
            <LinkField
              v-if="f.fieldtype === 'link'"
              :doctype="f.options"
              :label="f.label"
              :filters="f.filters || {}"
              :modelValue="values[f.fieldname] || ''"
              @update:modelValue="(v) => (values[f.fieldname] = v)"
            />
            <ComboField
              v-else-if="f.fieldtype === 'select'"
              :label="f.label"
              :options="f.selectOptions"
              :modelValue="values[f.fieldname]"
              @update:modelValue="(v) => (values[f.fieldname] = v)"
            />
            <!-- Attach: a real upload. Rendering these as text boxes would only let
                 someone paste a URL, which is not what a CR12 or a licence needs. -->
            <div v-else-if="f.fieldtype === 'attach'">
              <label class="mb-1 block text-xs text-ink-gray-5">{{ f.label }}</label>
              <div class="flex items-center gap-2">
                <FileUploader @success="(file) => (values[f.fieldname] = file.file_url)">
                  <template #default="{ openFileSelector, uploading }">
                    <Button
                      :loading="uploading"
                      :label="values[f.fieldname] ? 'Replace' : 'Upload'"
                      @click="openFileSelector()"
                    />
                  </template>
                </FileUploader>
                <a
                  v-if="values[f.fieldname]"
                  :href="values[f.fieldname]"
                  target="_blank"
                  rel="noopener"
                  class="truncate text-xs text-ink-blue-3 hover:underline"
                >
                  View file
                </a>
                <span v-else class="text-xs text-ink-gray-5">Not uploaded</span>
              </div>
            </div>
            <FormControl
              v-else-if="f.fieldtype === 'check'"
              type="checkbox"
              :label="f.label"
              :modelValue="!!values[f.fieldname]"
              @update:modelValue="(v) => (values[f.fieldname] = v ? 1 : 0)"
            />
            <FormControl
              v-else
              :type="fcType(f.fieldtype)"
              :label="f.label"
              v-model="values[f.fieldname]"
            />
          </template>
          </div>
        </div>

        <ItemsTable
          v-for="child in childConfigs"
          :key="child.fieldname"
          :title="child.title"
          :columns="child.columns"
          :modelValue="values[child.fieldname]"
          :doctype="config.doctype"
          :party="partyValue"
          :company="values.company || ''"
          :warehouse="values.set_warehouse || values.warehouse || ''"
          :currency="values.currency || ''"
          @update:modelValue="(v) => (values[child.fieldname] = v)"
        />

        <ErrorMessage :message="error" />
      </div>
    </template>
    <template #actions="{ close }">
      <div class="flex justify-end gap-2">
        <Button label="Cancel" @click="close" />
        <Button variant="solid" :label="'Create ' + (config?.label || '')" :loading="loading" @click="create" />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, reactive, watch, computed } from 'vue'
import { Dialog, Button, FormControl, ErrorMessage, FileUploader, call } from 'frappe-ui'
import LinkField from '@/components/LinkField.vue'
import ComboField from '@/components/ComboField.vue'
import ItemsTable from '@/components/ItemsTable.vue'
import { getDefaults } from '@/data/defaults.js'

const show = defineModel()
const props = defineProps({
  config: Object,
  // Values mapped from a source document ("Create Sales Invoice" off an order).
  // They land on top of the defaults, so the form opens ready to review.
  prefill: { type: Object, default: null },
})
const emit = defineEmits(['created'])

// `child` is the single-table form the app started with; `children` lets a form carry
// several (a sales order has its items *and* its sales team).
const childConfigs = computed(() => props.config?.children || (props.config?.child ? [props.config.child] : []))

const values = reactive({})
const partyValue = computed(() => values.customer || values.supplier || values.party_name || '')
const error = ref('')
const loading = ref(false)
// Which of the declared fields this site actually has, and what the site calls them.
const fieldMeta = ref(null)
// Mandatory fields this site has that the app does not declare — a live site adds its
// own (bill of lading, vehicle, commission) and the document will not submit without
// them, so the form has to ask.
const requiredFields = ref([])

// A field survives when the doctype really has it. Some of the fields the forms ask
// for are site customisations (a verification status, the KYC attachments), and a
// form that showed them on a site without them would collect values nothing reads.
const visibleFields = computed(() => {
  const declared = [...(props.config?.fields || []), ...requiredFields.value]
  if (!fieldMeta.value) return declared
  return declared
    .filter((f) => f.virtual || (fieldMeta.value[f.fieldname] && !fieldMeta.value[f.fieldname].read_only))
    .map((f) => {
      if (f.virtual) return f
      const meta = fieldMeta.value[f.fieldname]
      return {
        ...f,
        label: f.label || meta.label,
        // Select options come from the site, so a customised list stays correct.
        selectOptions: f.selectOptions || meta.select_options,
      }
    })
})

// Fields are laid out in the order declared; `section` on a field starts a new group.
const groups = computed(() => {
  const out = []
  for (const f of visibleFields.value) {
    if (!out.length || (f.section && f.section !== out[out.length - 1].title)) {
      out.push({ title: f.section || '', fields: [] })
    }
    out[out.length - 1].fields.push(f)
  }
  return out
})

function fcType(ft) {
  if (ft === 'float' || ft === 'currency') return 'number'
  if (ft === 'date') return 'date'
  if (ft === 'textarea') return 'textarea'
  return 'text'
}

function today() {
  return new Date().toISOString().slice(0, 10)
}

const SPECIAL = ['company', 'warehouse', 'selling_price_list', 'buying_price_list']

async function loadRequiredFields() {
  requiredFields.value = []
  if (!props.config?.doctype) return
  try {
    const extra = await call('kamil.api.get_missing_mandatory_fields', {
      doctype: props.config.doctype,
      known: JSON.stringify((props.config.fields || []).map((f) => f.fieldname)),
    })
    requiredFields.value = (extra || []).map((f) => ({ ...f, section: 'Required', virtual: true }))
  } catch (e) {
    requiredFields.value = []
  }
}

async function loadFieldMeta() {
  fieldMeta.value = null
  const fields = props.config?.fields || []
  if (!fields.length) return
  try {
    fieldMeta.value = await call('kamil.api.get_form_field_meta', {
      doctype: props.config.doctype,
      fieldnames: JSON.stringify(fields.filter((f) => !f.virtual).map((f) => f.fieldname)),
    })
  } catch (e) {
    // Fall back to showing everything declared rather than an empty form.
    fieldMeta.value = null
  }
}

async function reset() {
  Object.keys(values).forEach((k) => delete values[k])
  error.value = ''
  if (!props.config) return
  loadFieldMeta()
  loadRequiredFields()
  const d = (await getDefaults()) || {}
  for (const f of props.config.fields || []) {
    if (f.default === 'today') values[f.fieldname] = today()
    else if (SPECIAL.includes(f.default)) values[f.fieldname] = d[f.default] || ''
    else if (f.default !== undefined) values[f.fieldname] = f.default
  }
  for (const child of childConfigs.value) values[child.fieldname] = [{}]

  for (const [field, value] of Object.entries(props.prefill || {})) {
    if (value === null || value === undefined || value === '') continue
    values[field] = value
  }
  // A mapped document brings its own rows; an empty starter row would be noise.
  for (const child of childConfigs.value) {
    const incoming = props.prefill?.[child.fieldname]
    if (Array.isArray(incoming) && incoming.length) {
      values[child.fieldname] = incoming.map((row) => ({ ...row }))
    }
  }
}

// `immediate` matters: a dialog rendered with v-if mounts with `show` already true,
// and a plain watcher would never fire — leaving the form blank instead of prefilled.
watch(show, (v) => v && reset(), { immediate: true })

// A field can be derived from another (payroll's end date follows its start date).
// Recomputed whenever the source changes, and still editable afterwards.
watch(
  () => visibleFields.value.map((f) => (f.deriveFrom ? values[f.deriveFrom] : '')).join('|'),
  () => {
    for (const f of visibleFields.value) {
      if (!f.deriveFrom || typeof f.derive !== 'function') continue
      const source = values[f.deriveFrom]
      if (source) values[f.fieldname] = f.derive(source, values)
    }
  },
)
// A second "Create from" while this dialog is still mounted brings new values.
watch(() => props.prefill, () => show.value && reset())

function clean() {
  const out = {}
  for (const [k, v] of Object.entries(values)) {
    if (Array.isArray(v)) {
      const rows = v.filter((r) => Object.values(r).some((x) => x !== '' && x !== null && x !== undefined))
      if (rows.length) out[k] = rows
    } else if (v !== '' && v !== null && v !== undefined) {
      out[k] = v
    }
  }
  return out
}

async function create() {
  error.value = ''
  const missing = visibleFields.value.filter(
    (f) => f.reqd && f.fieldtype !== 'check' && !values[f.fieldname],
  )
  if (missing.length) {
    error.value = `Please fill in: ${missing.map((f) => f.label).join(', ')}`
    return
  }
  loading.value = true
  try {
    // A doctype can name its own creator when one record is not the whole story —
    // a customer also gets its contact and address.
    const payload = props.config.method
      ? { values: JSON.stringify(clean()) }
      : { doctype: props.config.doctype, values: JSON.stringify(clean()) }
    const out = await call(props.config.method || 'kamil.api.create_document', payload)
    emit('created', out)
    show.value = false
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not create record.'
  } finally {
    loading.value = false
  }
}
</script>
