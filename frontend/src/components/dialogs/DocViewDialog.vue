<template>
  <Dialog v-model="show" :options="{ title: name || 'Document', size: '3xl' }">
    <template #body-content>
      <div v-if="loading" class="p-6 text-center text-sm text-ink-gray-5">Loading…</div>
      <div v-else-if="doc" class="space-y-5">
        <!-- Summary -->
        <div class="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
          <div v-for="c in columns" :key="c.field">
            <div class="text-xs text-ink-gray-5">{{ c.label }}</div>
            <div class="mt-0.5 text-sm">
              <Badge v-if="c.type === 'status'" :theme="statusTheme(doc[c.field])" :label="doc[c.field] || 'Draft'" />
              <span v-else-if="c.type === 'currency'" class="tabular-nums text-ink-gray-8">{{ money(doc[c.field], doc[currencyField]) }}</span>
              <span v-else-if="c.type === 'date'" class="text-ink-gray-7">{{ fmtDate(doc[c.field]) }}</span>
              <span v-else class="text-ink-gray-8">{{ doc[c.field] }}</span>
            </div>
          </div>
        </div>

        <!-- Child rows -->
        <div v-if="child && childRows.length" class="rounded-lg border border-outline-gray-1">
          <div class="border-b border-outline-gray-1 px-3 py-2 text-sm font-semibold text-ink-gray-8">{{ child.title }}</div>
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-outline-gray-1 text-left text-xs text-ink-gray-5">
                <th v-for="col in child.columns" :key="col.fieldname" class="px-3 py-1.5 font-medium">{{ col.label }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, i) in childRows" :key="i" class="border-b border-outline-gray-1 last:border-0">
                <td v-for="col in child.columns" :key="col.fieldname" class="px-3 py-1.5 text-ink-gray-7">
                  <span v-if="col.fieldtype === 'currency'" class="tabular-nums">{{ money(r[col.fieldname], doc[currencyField]) }}</span>
                  <span v-else>{{ r[col.fieldname] }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <ErrorMessage :message="error" />
      </div>
    </template>
    <template #actions="{ close }">
      <div class="flex w-full items-center justify-between gap-2">
        <Button label="Open in ERPNext" @click="openDesk">
          <template #prefix><ExternalLink class="h-4 w-4" /></template>
        </Button>
        <div class="flex gap-2">
          <Button label="Close" @click="close" />
          <Button v-if="canSubmit" variant="solid" label="Submit" :loading="submitting" @click="submit" />
        </div>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Dialog, Button, Badge, ErrorMessage, call } from 'frappe-ui'
import ExternalLink from '~icons/lucide/external-link'

const show = defineModel()
const props = defineProps({
  doctype: { type: String, required: true },
  name: { type: String, default: '' },
  columns: { type: Array, default: () => [] },
  child: { type: Object, default: null },
  currencyField: { type: String, default: 'currency' },
})
const emit = defineEmits(['submitted'])

const NON_SUBMITTABLE = ['Item']

const doc = ref(null)
const loading = ref(false)
const submitting = ref(false)
const error = ref('')

const childRows = computed(() => (doc.value && props.child ? doc.value[props.child.fieldname] || [] : []))
const canSubmit = computed(
  () => doc.value && doc.value.docstatus === 0 && !NON_SUBMITTABLE.includes(props.doctype),
)

async function load() {
  if (!props.name) return
  loading.value = true
  error.value = ''
  doc.value = null
  try {
    doc.value = await call('frappe.client.get', { doctype: props.doctype, name: props.name })
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not load document.'
  } finally {
    loading.value = false
  }
}

watch(show, (v) => {
  if (v) load()
})

function openDesk() {
  const slug = props.doctype.toLowerCase().replace(/ /g, '-')
  window.location.href = `/app/${slug}/${encodeURIComponent(props.name)}`
}

async function submit() {
  submitting.value = true
  error.value = ''
  try {
    await call('kamil.api.submit_document', { doctype: props.doctype, name: props.name })
    show.value = false
    emit('submitted')
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not submit document.'
  } finally {
    submitting.value = false
  }
}

function money(v, c) {
  if (v === null || v === undefined) return ''
  try {
    return new Intl.NumberFormat('en-KE', { style: 'currency', currency: c || 'KES', maximumFractionDigits: 0 }).format(v)
  } catch {
    return v
  }
}
function fmtDate(v) {
  if (!v) return ''
  return new Date(v).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}
function statusTheme(status) {
  const map = { Paid: 'green', Completed: 'green', Submitted: 'blue', Draft: 'gray', Unpaid: 'orange', Overdue: 'red', Cancelled: 'red', Return: 'gray', 'Partly Paid': 'orange', 'To Bill': 'orange', 'To Deliver': 'orange', 'To Receive': 'orange', 'On Hold': 'red' }
  return map[status] || 'gray'
}
</script>
