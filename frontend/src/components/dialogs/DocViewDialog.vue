<template>
  <Dialog v-model="show" :options="{ title: curName || 'Document', size: '3xl' }">
    <template #body-content>
      <div v-if="loading" class="p-6 text-center text-sm text-ink-gray-5">Loading…</div>
      <div v-else-if="doc" class="space-y-5">
        <div class="flex flex-wrap items-center gap-2">
          <span class="text-xs font-medium uppercase tracking-wide text-ink-gray-4">{{ curDoctype }}</span>
          <!-- With a workflow attached, its state is the document's real status -->
          <Badge
            v-if="actions.workflow && actions.workflow_state"
            :theme="statusTheme(actions.workflow_state)"
            :label="actions.workflow_state"
          />
        </div>

        <!-- Edit form: the same field list the create dialog uses, pre-filled. -->
        <div v-if="editing" class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <template v-for="f in editFields" :key="f.fieldname">
            <LinkField
              v-if="f.fieldtype === 'link'"
              :doctype="f.options"
              :label="f.label"
              :filters="f.filters || {}"
              :modelValue="editValues[f.fieldname] || ''"
              @update:modelValue="(v) => (editValues[f.fieldname] = v)"
            />
            <ComboField
              v-else-if="f.fieldtype === 'select'"
              :label="f.label"
              :options="f.selectOptions"
              :modelValue="editValues[f.fieldname]"
              @update:modelValue="(v) => (editValues[f.fieldname] = v)"
            />
            <div v-else-if="f.fieldtype === 'attach'">
              <label class="mb-1 block text-xs text-ink-gray-5">{{ f.label }}</label>
              <div class="flex items-center gap-2">
                <FileUploader @success="(file) => (editValues[f.fieldname] = file.file_url)">
                  <template #default="{ openFileSelector, uploading }">
                    <Button
                      :loading="uploading"
                      :label="editValues[f.fieldname] ? 'Replace' : 'Upload'"
                      @click="openFileSelector()"
                    />
                  </template>
                </FileUploader>
                <a
                  v-if="editValues[f.fieldname]"
                  :href="editValues[f.fieldname]"
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
              :type="editType(f.fieldtype)"
              :label="f.label"
              v-model="editValues[f.fieldname]"
            />
          </template>
        </div>

        <!-- Summary -->
        <div v-else class="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
          <div v-for="c in filledColumns" :key="c.field">
            <div class="text-xs text-ink-gray-5">{{ c.label }}</div>
            <div class="mt-0.5 text-sm">
              <Badge v-if="c.type === 'status'" :theme="statusTheme(doc[c.field])" :label="doc[c.field] || 'Draft'" />
              <Badge
                v-else-if="c.type === 'docstatus'"
                :theme="docstatusBadge(doc[c.field]).theme"
                :label="docstatusBadge(doc[c.field]).label"
              />
              <Badge v-else-if="c.type === 'kind' && doc[c.field]" :theme="kindTheme(doc[c.field])" :label="doc[c.field]" />
              <span v-else-if="c.type === 'currency'" class="tabular-nums text-ink-gray-8">{{ money(doc[c.field], doc[curCurrency]) }}</span>
              <span v-else-if="c.type === 'date'" class="text-ink-gray-7">{{ fmtDate(doc[c.field]) }}</span>
              <span v-else-if="c.type === 'ago'" class="text-ink-gray-6">{{ fmtDate(doc[c.field]) }}</span>
              <span v-else class="text-ink-gray-8">{{ doc[c.field] }}</span>
            </div>
          </div>
        </div>

        <!-- Child rows -->
        <div v-if="curChild && childRows.length" class="rounded-lg border border-outline-gray-1">
          <div class="border-b border-outline-gray-1 px-3 py-2 text-sm font-semibold text-ink-gray-8">{{ curChild.title }}</div>
          <div class="overflow-x-auto">
            <table class="w-full min-w-[420px] text-sm">
              <thead>
                <tr class="border-b border-outline-gray-1 text-left text-xs text-ink-gray-5">
                  <th v-for="col in curChild.columns" :key="col.fieldname" class="px-3 py-1.5 font-medium">{{ col.label }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(r, i) in childRows" :key="i" class="border-b border-outline-gray-1 last:border-0">
                  <td v-for="col in curChild.columns" :key="col.fieldname" class="px-3 py-1.5 text-ink-gray-7">
                    <span v-if="col.fieldtype === 'currency'" class="tabular-nums">{{ money(r[col.fieldname], doc[curCurrency]) }}</span>
                    <span v-else>{{ r[col.fieldname] }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Under a workflow with nothing this user may do from the current state -->
        <div
          v-if="actions.workflow && !workflowActions.length && !isCancelled"
          class="rounded-lg border border-outline-gray-1 bg-surface-gray-1 p-3 text-sm text-ink-gray-6"
        >
          This document follows the <span class="font-medium">{{ actions.workflow }}</span> approval
          flow<span v-if="actions.workflow_state">, and is currently
          <span class="font-medium">{{ actions.workflow_state }}</span></span>. There is nothing for
          you to action on it right now.
        </div>

        <!-- Why this document was cancelled (shown for anything already cancelled) -->
        <div v-if="isCancelled" class="space-y-1 rounded-lg border border-red-200 bg-red-50 p-3">
          <div class="flex items-center gap-2 text-sm font-semibold text-red-700">
            <Ban class="h-4 w-4" /> Cancelled
          </div>
          <p v-if="cancelReason.reason" class="text-sm text-ink-gray-8">{{ cancelReason.reason }}</p>
          <p v-else class="text-sm italic text-ink-gray-5">No reason was recorded for this cancellation.</p>
          <p v-if="cancelReason.by" class="text-xs text-ink-gray-5">
            by {{ cancelReason.by }}<span v-if="cancelReason.on"> · {{ fmtDate(cancelReason.on) }}</span>
          </p>
        </div>

        <!-- Cancel confirmation -->
        <div v-if="cancelOpen" class="space-y-3 rounded-lg border border-red-200 bg-red-50 p-3">
          <div class="flex items-center gap-2 text-sm font-semibold text-red-700">
            <Ban class="h-4 w-4" /> Cancel this document?
          </div>
          <p class="text-sm text-ink-gray-7">
            Cancelling reverses its accounting and stock entries. This cannot be undone —
            you would need to amend the document instead.
          </p>
          <FormControl
            type="textarea"
            label="Reason for cancelling (required)"
            placeholder="e.g. Duplicate entry — customer was invoiced twice"
            v-model="cancelReasonInput"
          />
          <div class="flex justify-end gap-2">
            <Button label="Keep it" @click="cancelOpen = false" />
            <Button
              theme="red"
              variant="solid"
              label="Yes, cancel it"
              :loading="cancelling"
              :disabled="!cancelReasonInput.trim()"
              @click="cancelDoc"
            />
          </div>
        </div>

        <!-- Raise a payment request against this document -->
        <div v-if="prOpen" class="space-y-3 rounded-lg border border-outline-gray-1 bg-surface-gray-1 p-3">
          <div class="flex flex-wrap items-center gap-2 text-sm font-semibold text-ink-gray-8">
            <Send class="h-4 w-4 text-ink-gray-6" /> Request payment
            <Badge v-if="prOutstanding" theme="orange" :label="`Outstanding ${money(prOutstanding, doc[curCurrency])}`" />
          </div>
          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <FormControl type="number" label="Amount to request" v-model="prForm.amount" />
            <ComboField
              label="Mode of Payment"
              :options="modeOptions"
              create-doctype="Mode of Payment"
              :modelValue="prForm.mode_of_payment"
              @update:modelValue="(v) => (prForm.mode_of_payment = v || '')"
              @created="loadModes"
            />
            <FormControl type="text" label="Approver email" placeholder="approver@company.com" v-model="prForm.recipient" />
            <FormControl type="text" label="Approver WhatsApp (optional)" placeholder="+2547…" v-model="prForm.phone_number" />
          </div>
          <div class="flex flex-wrap items-center gap-4">
            <FormControl type="checkbox" label="Send email" v-model="prForm.via_email" />
            <FormControl type="checkbox" label="Send WhatsApp" v-model="prForm.via_whatsapp" />
          </div>
          <div v-if="prResult" class="space-y-1 rounded-lg border p-2 text-sm" :class="prResult.ok ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'">
            <div :class="prResult.ok ? 'font-medium text-green-700' : 'font-medium text-red-700'">{{ prResult.title }}</div>
            <div v-for="line in prResult.lines" :key="line" class="break-all text-ink-gray-7">{{ line }}</div>
          </div>
          <div class="flex flex-wrap justify-end gap-2">
            <Button label="Close" @click="prOpen = false" />
            <Button variant="solid" label="Raise request" :loading="prSaving" @click="raisePaymentRequest" />
          </div>
        </div>

        <!-- Money in against this invoice -->
        <div v-if="payOpen" class="space-y-3 rounded-lg border border-outline-gray-1 bg-surface-gray-1 p-3">
          <div class="flex flex-wrap items-center gap-2 text-sm font-semibold text-ink-gray-8">
            <Wallet class="h-4 w-4 text-ink-gray-6" /> Record payment
            <Badge theme="orange" :label="`Outstanding ${money(doc.outstanding_amount, doc[curCurrency])}`" />
          </div>
          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <FormControl type="number" label="Amount received" v-model="payForm.amount" />
            <ComboField
              label="Mode of Payment"
              :options="modeOptions"
              create-doctype="Mode of Payment"
              :modelValue="payForm.mode_of_payment"
              @update:modelValue="(v) => (payForm.mode_of_payment = v || '')"
              @created="loadModes"
            />
            <FormControl type="text" label="Reference no." placeholder="M-Pesa code, cheque or slip no." v-model="payForm.reference_no" />
            <FormControl type="date" label="Reference date" v-model="payForm.reference_date" />
          </div>
          <p class="text-xs text-ink-gray-5">
            Creates a draft payment entry allocated against this invoice — review and submit it
            from Payment Entries to settle the invoice. A bank or M-Pesa payment needs a
            reference number; ERPNext will not save one without it.
          </p>
          <div v-if="payResult" class="text-sm" :class="payOk ? 'text-green-600' : 'text-red-600'">{{ payResult }}</div>
          <div class="flex flex-wrap justify-end gap-2">
            <Button label="Close" @click="payOpen = false" />
            <Button variant="solid" label="Record payment" :loading="paySaving" @click="recordPayment" />
          </div>
        </div>

        <!-- Print panel -->
        <div v-if="printOpen" class="space-y-3 rounded-lg border border-outline-gray-1 bg-surface-gray-1 p-3">
          <div class="flex items-center gap-2 text-sm font-semibold text-ink-gray-8">
            <Printer class="h-4 w-4 text-ink-gray-6" /> Print
          </div>
          <ComboField label="Print format" :options="printFormats" :modelValue="printFormat" @update:modelValue="(v) => (printFormat = v || 'Standard')" />
          <div class="flex flex-wrap justify-end gap-2">
            <Button label="Cancel" @click="printOpen = false" />
            <Button label="Download PDF" @click="downloadPdf" />
            <Button variant="solid" label="Print" @click="openPrint" />
          </div>
        </div>

        <!-- WhatsApp panel -->
        <div v-if="waOpen" class="space-y-3 rounded-lg border border-outline-gray-1 bg-surface-gray-1 p-3">
          <div class="flex flex-wrap items-center gap-2 text-sm font-semibold text-ink-gray-8">
            <MessageCircle class="h-4 w-4 text-green-600" /> Send via WhatsApp
            <Badge v-if="waSender" theme="green" :label="`from ${waSender}`" />
            <span v-else class="text-xs font-normal text-ink-gray-5">no sender configured</span>
          </div>
          <!-- The gateway sleeps when idle, so opening this panel wakes it up -->
          <div class="flex items-center gap-1.5 text-xs" :class="waWarm.ok ? 'text-green-600' : 'text-ink-gray-5'">
            <Spinner v-if="waWarming" class="h-3 w-3" />
            <span>{{ waWarmLabel }}</span>
          </div>
          <ComboField v-if="senderOptions.length" label="Send from" :options="senderOptions" :modelValue="waSender" @update:modelValue="(v) => (waSender = v || '')" />
          <ComboField label="Attach print format" :options="printFormats" :modelValue="waFormat" @update:modelValue="(v) => (waFormat = v || 'Standard')" />
          <FormControl type="text" label="Phone (optional — auto-detected from party)" placeholder="+2547…" v-model="waPhone" />
          <FormControl type="textarea" label="Message (optional)" v-model="waMessage" />
          <div v-if="waResult" class="text-sm" :class="waOk ? 'text-green-600' : 'text-red-600'">{{ waResult }}</div>
          <div v-if="waWarning" class="rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
            {{ waWarning }}
          </div>
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
        <div class="flex flex-wrap gap-2">
          <Dropdown v-if="transitionOptions.length" :options="transitionOptions">
            <Button variant="solid" label="Create">
              <template #prefix><Plus class="h-4 w-4" /></template>
            </Button>
          </Dropdown>
          <Button v-if="canCancel" theme="red" label="Cancel doc" @click="cancelOpen = !cancelOpen">
            <template #prefix><Ban class="h-4 w-4" /></template>
          </Button>
          <Button v-if="canReceivePayment" label="Record payment" @click="togglePayment">
            <template #prefix><Wallet class="h-4 w-4 text-ink-gray-6" /></template>
          </Button>
          <Button v-if="canRequestPayment" label="Request payment" @click="togglePaymentRequest">
            <template #prefix><Send class="h-4 w-4 text-ink-gray-6" /></template>
          </Button>
          <Button v-if="isPaymentRequest" variant="solid" label="Review & approve" @click="openApproval">
            <template #prefix><CheckCircle class="h-4 w-4" /></template>
          </Button>
          <Button label="Open in ERPNext" @click="openDesk">
            <template #prefix><ExternalLink class="h-4 w-4" /></template>
          </Button>
          <Button v-if="partyLink" label="Ledger" @click="openLedger">
            <template #prefix><BookOpen class="h-4 w-4" /></template>
          </Button>
          <Button label="Print" @click="printOpen = !printOpen">
            <template #prefix><Printer class="h-4 w-4" /></template>
          </Button>
          <Button :label="waButtonLabel" @click="toggleWhatsApp">
            <template #prefix><MessageCircle class="h-4 w-4 text-green-600" /></template>
          </Button>
        </div>
        <div class="flex flex-wrap gap-2">
          <Button label="Close" @click="close" />
          <!-- Editing is offered only while a document is still a draft; once it is
               submitted its ledger entries exist and it must be amended instead. -->
          <Button v-if="canEdit && !editing" label="Edit" @click="startEdit">
            <template #prefix><Pencil class="h-4 w-4" /></template>
          </Button>
          <template v-if="editing">
            <Button label="Discard" @click="editing = false" />
            <Button variant="solid" label="Save" :loading="saving" @click="saveEdit" />
          </template>
          <!-- A workflow owns the document's progression: its actions replace Submit -->
          <Button
            v-for="t in workflowActions"
            :key="t.action"
            variant="solid"
            :theme="actionTheme(t.action)"
            :label="t.action"
            :loading="workflowBusy === t.action"
            @click="applyAction(t.action)"
          />
          <Button v-if="canSubmit" variant="solid" label="Submit" :loading="submitting" @click="submit" />
        </div>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Dialog, Button, Badge, ErrorMessage, FormControl, Dropdown, Spinner, FileUploader, call } from 'frappe-ui'
import ExternalLink from '~icons/lucide/external-link'
import MessageCircle from '~icons/lucide/message-circle'
import Printer from '~icons/lucide/printer'
import Send from '~icons/lucide/send'
import Wallet from '~icons/lucide/wallet'
import BookOpen from '~icons/lucide/book-open'
import Plus from '~icons/lucide/plus'
import Ban from '~icons/lucide/ban'
import Pencil from '~icons/lucide/pencil'
import CheckCircle from '~icons/lucide/check-circle'
import ComboField from '@/components/ComboField.vue'
import LinkField from '@/components/LinkField.vue'
import { findList } from '@/data/doctypes.js'
import { statusTheme, kindTheme, docstatusBadge } from '@/utils/status.js'
import { defaultCurrency } from '@/utils/money.js'

const router = useRouter()
const show = defineModel()
const props = defineProps({
  doctype: { type: String, required: true },
  name: { type: String, default: '' },
  columns: { type: Array, default: () => [] },
  child: { type: Object, default: null },
  currencyField: { type: String, default: 'currency' },
})
const emit = defineEmits(['submitted', 'create-from'])

// What the server says this document may do: submit/cancel, or — when a workflow is
// attached — only the transitions the workflow allows this user right now.
const EMPTY_ACTIONS = {
  docstatus: 0,
  is_submittable: false,
  can_submit: false,
  can_cancel: false,
  workflow: null,
  workflow_state: null,
  transitions: [],
}

// The document currently shown — starts from props, can be re-targeted in place
// (e.g. after "Create Purchase Receipt" we show the new PR without leaving).
const curDoctype = ref(props.doctype)
const curName = ref(props.name)
const curColumns = ref(props.columns)
const curChild = ref(props.child)
const curCurrency = ref(props.currencyField)

const doc = ref(null)
const loading = ref(false)
const submitting = ref(false)
const error = ref('')
const actions = ref({ ...EMPTY_ACTIONS })
const workflowBusy = ref('')

const transitions = ref([])
const printFormats = ref([{ label: 'Standard', value: 'Standard' }])
const printFormat = ref('Standard')
const printOpen = ref(false)
const cancelOpen = ref(false)
const cancelling = ref(false)
const cancelReasonInput = ref('')
const cancelReason = ref({})

// Raising a payment request straight off an invoice or order — the same flow the
// Payment Requests list offers, without having to go and find the document again.
const prOpen = ref(false)
const prSaving = ref(false)
const prResult = ref(null)
const prForm = reactive({
  amount: null,
  mode_of_payment: '',
  recipient: '',
  phone_number: '',
  via_email: true,
  via_whatsapp: false,
})
const modeOptions = ref([])

// Receiving money against a sales invoice. Buying works the other way round — a
// payment there goes through the request-and-approve flow, not straight out.
const payOpen = ref(false)
const paySaving = ref(false)
const payResult = ref('')
const payOk = ref(false)
const payForm = reactive({ amount: null, mode_of_payment: '', reference_no: '', reference_date: '' })

const waOpen = ref(false)
const waPhone = ref('')
const waMessage = ref('')
const waSending = ref(false)
const waResult = ref('')
const waWarning = ref('')
const waOk = ref(false)
const waWarming = ref(false)
const waWarm = ref({ ok: false, took: 0 })
const senderOptions = ref([])
const waSender = ref('')
const waFormat = ref('Standard')

const childRows = computed(() => (doc.value && curChild.value ? doc.value[curChild.value.fieldname] || [] : []))
const canCancel = computed(() => !!doc.value && doc.value.docstatus === 1 && actions.value.can_cancel !== false)
const isCancelled = computed(() => doc.value && doc.value.docstatus === 2)
// Submit is offered only when nothing else governs the document. Anything under a
// workflow has to go through its approvals instead, so the button is hidden there.
const canSubmit = computed(() => !!doc.value && !actions.value.workflow && actions.value.can_submit)
const workflowActions = computed(() => (actions.value.workflow ? actions.value.transitions || [] : []))
const isPaymentRequest = computed(() => curDoctype.value === 'Payment Request')

// A payment can be requested against a submitted invoice or order. Requests are
// raised against the document, so drafts and cancelled documents are out.
// Buying only: a payment request is how the company asks to pay someone, so raising
// one against our own sales document makes no sense.
const PAYABLE_DOCTYPES = ['Purchase Invoice', 'Purchase Order']
const canRequestPayment = computed(
  () => !!doc.value && doc.value.docstatus === 1 && PAYABLE_DOCTYPES.includes(curDoctype.value),
)
const canReceivePayment = computed(
  () =>
    !!doc.value &&
    doc.value.docstatus === 1 &&
    curDoctype.value === 'Sales Invoice' &&
    Number(doc.value.outstanding_amount) > 0,
)

const prOutstanding = computed(() => {
  const d = doc.value
  if (!d) return 0
  const outstanding = Number(d.outstanding_amount)
  if (Number.isFinite(outstanding) && outstanding > 0) return outstanding
  // Orders track what has been paid rather than what is left.
  return Math.max(Number(d.grand_total || 0) - Number(d.advance_paid || 0), 0)
})

const slugFor = (doctype) => (doctype || '').toLowerCase().replace(/ /g, '-')

// --- editing -----------------------------------------------------------------
const editing = ref(false)
const saving = ref(false)
const editValues = ref({})

// The list config already describes this doctype's fields for the create dialog;
// reuse that rather than maintaining a second field list per doctype.
const editFields = computed(() => findList(slugFor(curDoctype.value))?.create?.fields || [])

// Draft only. A submitted document owns ledger entries and must be amended.
const canEdit = computed(
  () => !!doc.value && doc.value.docstatus === 0 && editFields.value.length > 0,
)

function startEdit() {
  const next = {}
  for (const f of editFields.value) next[f.fieldname] = doc.value?.[f.fieldname] ?? ''
  editValues.value = next
  error.value = ''
  editing.value = true
}

function editType(ft) {
  if (ft === 'float' || ft === 'currency') return 'number'
  if (ft === 'date') return 'date'
  if (ft === 'textarea') return 'textarea'
  return 'text'
}

async function saveEdit() {
  saving.value = true
  error.value = ''
  try {
    await call('kamil.api.update_document', {
      doctype: curDoctype.value,
      name: curName.value,
      values: JSON.stringify(editValues.value),
    })
    editing.value = false
    emit('submitted') // refresh the list behind the dialog
    await load()
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not save the changes.'
  } finally {
    saving.value = false
  }
}
// Which fields actually have a value. `name` always shows, so an empty record still
// identifies itself.
const filledColumns = computed(() => {
  const d = doc.value || {}
  return curColumns.value.filter((c) => {
    if (c.field === 'name') return true
    const v = d[c.field]
    return v !== null && v !== undefined && v !== '' && v !== 0
  })
})

const partyLink = computed(() => {
  const d = doc.value
  if (!d) return null
  // A customer or supplier record is itself the party — its ledger is one click away.
  if (['Customer', 'Supplier'].includes(curDoctype.value)) {
    return { party_type: curDoctype.value, party: d.name }
  }
  if (d.customer) return { party_type: 'Customer', party: d.customer }
  if (d.supplier) return { party_type: 'Supplier', party: d.supplier }
  if (d.party_type && d.party) return { party_type: d.party_type, party: d.party }
  return null
})
const waButtonLabel = computed(() => (waSender.value ? `WhatsApp · ${waSender.value}` : 'WhatsApp'))
const transitionOptions = computed(() =>
  transitions.value.map((t) => ({ label: `Create ${t.target}`, onClick: () => makeNext(t.target) })),
)

function resetPanels() {
  editing.value = false
  error.value = ''
  actions.value = { ...EMPTY_ACTIONS }
  printOpen.value = false
  prOpen.value = false
  prResult.value = null
  payOpen.value = false
  payResult.value = ''
  cancelOpen.value = false
  cancelReasonInput.value = ''
  cancelReason.value = {}
  waOpen.value = false
  waResult.value = ''
  waWarning.value = ''
}

async function load() {
  if (!curName.value) return
  loading.value = true
  resetPanels()
  doc.value = null
  try {
    doc.value = await call('frappe.client.get', { doctype: curDoctype.value, name: curName.value })
    try {
      actions.value = {
        ...EMPTY_ACTIONS,
        ...((await call('kamil.api.get_doc_actions', { doctype: curDoctype.value, name: curName.value })) || {}),
      }
    } catch (e) {
      // Fall back to offering nothing rather than a button that is bound to fail.
      actions.value = { ...EMPTY_ACTIONS }
    }
    if (doc.value?.docstatus === 2) {
      try {
        cancelReason.value =
          (await call('kamil.api.get_cancellation_reason', {
            doctype: curDoctype.value,
            name: curName.value,
          })) || {}
      } catch (e) {
        cancelReason.value = {}
      }
    }
    try {
      transitions.value = (await call('kamil.api.get_doc_transitions', { doctype: curDoctype.value })) || []
    } catch (e) {
      transitions.value = []
    }
    try {
      printFormats.value = (await call('kamil.api.get_print_formats', { doctype: curDoctype.value })) || [
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
  if (v) {
    // (re)initialise from props each time it's opened from a list
    curDoctype.value = props.doctype
    curName.value = props.name
    curColumns.value = props.columns
    curChild.value = props.child
    curCurrency.value = props.currencyField
    waPhone.value = ''
    waMessage.value = ''
    load()
  }
})

async function makeNext(target) {
  error.value = ''
  try {
    // Map the source onto the target and open the form on those values — nothing is
    // written until the user presses Create, exactly as on the desk.
    const draft = await call('kamil.api.get_next_document_draft', {
      doctype: curDoctype.value,
      name: curName.value,
      target,
    })
    const cfg = findList(slugFor(target))
    if (cfg?.create) {
      show.value = false
      emit('create-from', { target, config: cfg.create, values: draft?.values || {} })
      return
    }

    // No form for this target in the app — fall back to creating the draft directly.
    const out = await call('kamil.api.make_next_document', {
      doctype: curDoctype.value,
      name: curName.value,
      target,
    })
    emit('submitted')
    curDoctype.value = out?.doctype || target
    curName.value = out?.name
    curColumns.value = cfg?.view || cfg?.columns || []
    curChild.value = cfg?.create?.child || null
    curCurrency.value = cfg?.currencyField ?? 'currency'
    waPhone.value = ''
    await load()
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not create the document.'
  }
}

function openApproval() {
  show.value = false
  router.push(`/payment-approval/${encodeURIComponent(curName.value)}`)
}

function openDesk() {
  const slug = curDoctype.value.toLowerCase().replace(/ /g, '-')
  window.location.href = `/app/${slug}/${encodeURIComponent(curName.value)}`
}

async function submit() {
  submitting.value = true
  error.value = ''
  try {
    await call('kamil.api.submit_document', { doctype: curDoctype.value, name: curName.value })
    show.value = false
    emit('submitted')
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not submit document.'
  } finally {
    submitting.value = false
  }
}

// Approve/Submit-style actions read as positive, rejections as destructive.
function actionTheme(action) {
  const a = String(action).toLowerCase()
  if (/reject|cancel|decline|return/.test(a)) return 'red'
  return 'blue'
}

async function applyAction(action) {
  workflowBusy.value = action
  error.value = ''
  try {
    await call('kamil.api.apply_workflow_action', {
      doctype: curDoctype.value,
      name: curName.value,
      action,
    })
    emit('submitted') // the source list's state has changed
    await load()
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not complete that action.'
  } finally {
    workflowBusy.value = ''
  }
}

async function cancelDoc() {
  const reason = cancelReasonInput.value.trim()
  if (!reason) return
  cancelling.value = true
  error.value = ''
  try {
    await call('kamil.api.cancel_document', {
      doctype: curDoctype.value,
      name: curName.value,
      reason,
    })
    cancelOpen.value = false
    emit('submitted')
    await load() // reloads with docstatus 2, which pulls the reason back in
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not cancel the document.'
  } finally {
    cancelling.value = false
  }
}

function openLedger() {
  if (!partyLink.value) return
  show.value = false
  router.push({ path: '/report/general-ledger', query: { ...partyLink.value } })
}

function printUrl(pdf) {
  const q = new URLSearchParams({ doctype: curDoctype.value, name: curName.value, format: printFormat.value || 'Standard', no_letterhead: '0' })
  if (!pdf) q.set('trigger_print', '1')
  return pdf ? `/api/method/frappe.utils.print_format.download_pdf?${q.toString()}` : `/printview?${q.toString()}`
}
function openPrint() {
  window.open(printUrl(false), '_blank')
}
function downloadPdf() {
  window.open(printUrl(true), '_blank')
}

const waWarmLabel = computed(() => {
  if (waWarming.value) return 'Waking the WhatsApp gateway…'
  if (waWarm.value.ok) return 'WhatsApp gateway ready'
  return 'WhatsApp gateway did not answer the wake-up ping — sending will retry it.'
})

/** The gateway sleeps when idle, so nudge it as soon as the panel is opened. */
async function warmGateway() {
  waWarming.value = true
  try {
    const res = await call('kamil.api.warm_whatsapp')
    waWarm.value = { ok: !!res?.awake, took: res?.took_ms || 0 }
  } catch (e) {
    waWarm.value = { ok: false, took: 0 }
  } finally {
    waWarming.value = false
  }
}

async function toggleWhatsApp() {
  waOpen.value = !waOpen.value
  if (!waOpen.value) return

  warmGateway() // deliberately not awaited — the user fills the form while it wakes
  if (!waPhone.value) {
    try {
      const p = await call('kamil.api.resolve_document_phone', { doctype: curDoctype.value, name: curName.value })
      if (p) waPhone.value = p
    } catch (e) {
      /* leave blank */
    }
  }
}

async function sendWhatsApp() {
  waSending.value = true
  waResult.value = ''
  waWarning.value = ''
  try {
    const out = await call('kamil.api.send_document_whatsapp', {
      doctype: curDoctype.value,
      name: curName.value,
      phone_number: waPhone.value || null,
      message: waMessage.value || null,
      sender: waSender.value || null,
      print_format: waFormat.value || null,
    })
    waOk.value = out?.success !== false
    waResult.value = waOk.value
      ? `Sent to ${out?.phone_number || waPhone.value} via WhatsApp ✓`
      : out?.error || 'Failed to send.'
    // e.g. the site's URL is not reachable from the internet, so the PDF would not load
    waWarning.value = out?.warning || ''
    if (waOk.value) waWarm.value = { ok: true, took: 0 }
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
    return new Intl.NumberFormat('en-KE', { style: 'currency', currency: c || defaultCurrency(), maximumFractionDigits: 0 }).format(v)
  } catch {
    return v
  }
}
function fmtDate(v) {
  if (!v) return ''
  return new Date(v).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}
</script>
