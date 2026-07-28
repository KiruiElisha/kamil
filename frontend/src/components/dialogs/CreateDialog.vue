<template>
  <Dialog v-model="show" :options="{ title: config?.title || 'New', size: config?.child ? '3xl' : 'lg' }">
    <template #body-content>
      <div v-if="config" class="space-y-4">
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <template v-for="f in config.fields" :key="f.fieldname">
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
              v-else
              :type="fcType(f.fieldtype)"
              :label="f.label"
              v-model="values[f.fieldname]"
            />
          </template>
        </div>

        <ItemsTable
          v-if="config.child"
          :title="config.child.title"
          :columns="config.child.columns"
          :modelValue="values[config.child.fieldname]"
          :doctype="config.doctype"
          :party="partyValue"
          :company="values.company || ''"
          @update:modelValue="(v) => (values[config.child.fieldname] = v)"
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
const props = defineProps({ config: Object })
const emit = defineEmits(['created'])

const values = reactive({})
const partyValue = computed(() => values.customer || values.supplier || values.party_name || '')
const error = ref('')
const loading = ref(false)

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

async function reset() {
  Object.keys(values).forEach((k) => delete values[k])
  error.value = ''
  if (!props.config) return
  const d = (await getDefaults()) || {}
  for (const f of props.config.fields || []) {
    if (f.default === 'today') values[f.fieldname] = today()
    else if (SPECIAL.includes(f.default)) values[f.fieldname] = d[f.default] || ''
    else if (f.default !== undefined) values[f.fieldname] = f.default
  }
  if (props.config.child) values[props.config.child.fieldname] = [{}]
}

watch(show, (v) => {
  if (v) reset()
})

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
  loading.value = true
  try {
    const out = await call('kamil.api.create_document', { doctype: props.config.doctype, values: JSON.stringify(clean()) })
    emit('created', out)
    show.value = false
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not create record.'
  } finally {
    loading.value = false
  }
}
</script>
