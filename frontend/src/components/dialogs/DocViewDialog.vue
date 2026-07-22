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
          <div class="overflow-x-auto">
            <table class="w-full min-w-[420px] text-sm">
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
        </div>

        <!-- Print panel -->
        <div v-if="printOpen" class="space-y-3 rounded-lg border border-outline-gray-1 bg-surface-gray-1 p-3">
          <div class="flex items-center gap-2 text-sm font-semibold text-ink-gray-8">
            <Printer class="h-4 w-4 text-ink-gray-6" /> Print
          </div>
          <ComboField
            label="Print format"
            :options="printFormats"
            :modelValue="printFormat"
            @update:modelValue="(v) => (printFormat = v || 'Standard')"
          />
          <div class="flex flex-wrap justify-end gap-2">
            <Button label="Cancel" @click="printOpen = false" />
            <Button label="Download PDF" @click="downloadPdf" />
            <Button variant="solid" label="Print" @click="openPrint" />
          </div>
        </div>

        <!-- WhatsApp panel -->
        <div v-if="waOpen" class="space-y-3 rounded-lg border border-outline-gray-1 bg-surface-gray-1 p-3">
          <div class="flex items-center gap-2 text-sm font-semibold text-ink-gray-8">
            <MessageCircle class="h-4 w-4 text-green-600" /> Send via WhatsApp
          </div>
          <ComboField
            v-if="senderOptions.length"
            label="Send from"
            :options="senderOptions"
            :modelValue="waSender"
            @update:modelValue="(v) => (waSender = v || '')"
          />
          <ComboField
            label="Attach print format"
            :options="printFormats"
            :modelValue="waFormat"
            @update:modelValue="(v) => (waFormat = v || 'Standard')"
          />
          <FormControl type="text" label="Phone (optional — auto-detected from party)" placeholder="+2547…" v-model="waPhone" />
          <FormControl type="textarea" label="Message (optional)" v-model="waMessage" />
          <div v-if="waResult" class="text-sm" :class="waOk ? 'text-green-600' : 'text-red-600'">{{ waResult }}</div>
          <div class="flex justify-end gap-2">
            <Button label="Cancel" @click="waOpen = false" />
            <Button variant="solid" :loading="waSending" label="Send" @click="sendWhatsApp" />
          </div>
        </div>

        <ErrorMessage :message="error" />
      </div>
    </template>
    <template #actions="{ close }">
      <div class="flex w-full flex-wrap items-center justify-between gap-2">
        <div class="flex gap-2">
          <Button label="Open in ERPNext" @click="openDesk">
            <template #prefix><ExternalLink class="h-4 w-4" /></template>
          </Button>
          <Button v-if="partyLink" label="Ledger" @click="openLedger">
            <template #prefix><BookOpen class="h-4 w-4" /></template>
          </Button>
          <Button label="Print" @click="printOpen = !printOpen">
            <template #prefix><Printer class="h-4 w-4" /></template>
          </Button>
          <Button label="WhatsApp" @click="toggleWhatsApp">
            <template #prefix><MessageCircle class="h-4 w-4 text-green-600" /></template>
          </Button>
        </div>
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
import { Dialog, Button, Badge, ErrorMessage, FormControl, call } from 'frappe-ui'
import ExternalLink from '~icons/lucide/external-link'
import MessageCircle from '~icons/lucide/message-circle'
import Printer from '~icons/lucide/printer'
import BookOpen from '~icons/lucide/book-open'
import { useRouter } from 'vue-router'
import ComboField from '@/components/ComboField.vue'

const router = useRouter()
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

// WhatsApp state
const waOpen = ref(false)
const waPhone = ref('')
const waMessage = ref('')
const waSending = ref(false)
const waResult = ref('')
const waOk = ref(false)
const senderOptions = ref([])
const waSender = ref('')

// Print state
const printOpen = ref(false)
const printFormats = ref([{ label: 'Standard', value: 'Standard' }])
const printFormat = ref('Standard')
const waFormat = ref('Standard')

const partyLink = computed(() => {
  const d = doc.value
  if (!d) return null
  if (d.customer) return { party_type: 'Customer', party: d.customer }
  if (d.supplier) return { party_type: 'Supplier', party: d.supplier }
  if (d.party_type && d.party) return { party_type: d.party_type, party: d.party }
  return null
})
function openLedger() {
  if (!partyLink.value) return
  show.value = false
  router.push({ path: '/report/general-ledger', query: { ...partyLink.value } })
}

const childRows = computed(() => (doc.value && props.child ? doc.value[props.child.fieldname] || [] : []))
const canSubmit = computed(() => doc.value && doc.value.docstatus === 0 && !NON_SUBMITTABLE.includes(props.doctype))

async function load() {
  if (!props.name) return
  loading.value = true
  error.value = ''
  doc.value = null
  waOpen.value = false
  printOpen.value = false
  waResult.value = ''
  try {
    doc.value = await call('frappe.client.get', { doctype: props.doctype, name: props.name })
    try {
      printFormats.value = (await call('kamil.api.get_print_formats', { doctype: props.doctype })) || [
        { label: 'Standard', value: 'Standard' },
      ]
      printFormat.value = printFormats.value[0]?.value || 'Standard'
      waFormat.value = printFormat.value
    } catch (e) {
      printFormats.value = [{ label: 'Standard', value: 'Standard' }]
    }
    try {
      senderOptions.value = (await call('kamil.api.list_whatsapp_senders')) || []
      if (!waSender.value && senderOptions.value.length) waSender.value = senderOptions.value[0].value
    } catch (e) {
      senderOptions.value = []
    }
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

function printUrl(pdf) {
  const q = new URLSearchParams({
    doctype: props.doctype,
    name: props.name,
    format: printFormat.value || 'Standard',
    no_letterhead: '0',
  })
  if (!pdf) q.set('trigger_print', '1')
  return pdf
    ? `/api/method/frappe.utils.print_format.download_pdf?${q.toString()}`
    : `/printview?${q.toString()}`
}
function openPrint() {
  window.open(printUrl(false), '_blank')
}
function downloadPdf() {
  window.open(printUrl(true), '_blank')
}

async function toggleWhatsApp() {
  waOpen.value = !waOpen.value
  if (waOpen.value && !waPhone.value) {
    try {
      const p = await call('kamil.api.resolve_document_phone', { doctype: props.doctype, name: props.name })
      if (p) waPhone.value = p
    } catch (e) {
      /* leave blank; backend still auto-resolves on send */
    }
  }
}

async function sendWhatsApp() {
  waSending.value = true
  waResult.value = ''
  try {
    const out = await call('kamil.api.send_document_whatsapp', {
      doctype: props.doctype,
      name: props.name,
      phone_number: waPhone.value || null,
      message: waMessage.value || null,
      sender: waSender.value || null,
      print_format: waFormat.value || null,
    })
    waOk.value = out?.success !== false
    waResult.value = waOk.value ? 'Sent via WhatsApp ✓' : out?.error || 'Failed to send.'
  } catch (e) {
    waOk.value = false
    waResult.value = e?.messages?.join(', ') || e?.message || 'Failed to send.'
  } finally {
    waSending.value = false
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
