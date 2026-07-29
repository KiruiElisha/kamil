<template>
  <div class="mx-auto w-full min-h-0 max-w-2xl flex-1 overflow-auto p-3 md:p-5">
    <h2 class="text-lg font-semibold text-ink-gray-8">Payment approvals</h2>
    <p class="mt-1 text-sm text-ink-gray-5">
      Every payment request raised in the app goes to one approver. Set them here and the
      request forms fill themselves in — you can still override it on an individual request.
    </p>

    <div v-if="loading" class="mt-4 space-y-2">
      <Skeleton v-for="n in 4" :key="n" class="h-10 w-full" />
    </div>

    <div v-else-if="!settings.exists" class="mt-4 rounded-lg border border-outline-gray-1 bg-surface-gray-1 p-4 text-sm text-ink-gray-6">
      Settings are not installed on this site yet. Run <span class="font-medium">bench migrate</span>
      (or <span class="font-medium">bench execute kamil.setup.setup_kamil</span>) and reload.
    </div>

    <div v-else class="mt-4 space-y-4">
      <div class="space-y-3 rounded-xl border border-outline-gray-1 bg-surface-white p-4">
        <LinkField
          label="Payment approver"
          doctype="User"
          :filters="{ enabled: 1 }"
          :modelValue="form.payment_approver"
          @update:modelValue="onApproverChange"
        />
        <FormControl
          type="text"
          label="Approver email"
          placeholder="approvals@kamilenergy.com"
          v-model="form.payment_approver_email"
        />
        <p class="text-xs text-ink-gray-5">
          Leave blank to use the approver's own account email.
        </p>
        <FormControl
          type="text"
          label="Approver WhatsApp"
          placeholder="+2547…"
          v-model="form.payment_approver_phone"
        />

        <div class="flex flex-wrap items-center gap-4 border-t border-outline-gray-1 pt-3">
          <FormControl type="checkbox" label="Send approval requests by email" v-model="form.notify_by_email" />
          <FormControl type="checkbox" label="Send approval requests by WhatsApp" v-model="form.notify_by_whatsapp" />
        </div>

        <div v-if="notice" class="rounded-lg border p-3 text-sm" :class="notice.ok ? 'border-green-200 bg-green-50 text-green-700' : 'border-red-200 bg-red-50 text-red-700'">
          {{ notice.text }}
        </div>
        <ErrorMessage :message="error" />

        <div v-if="!settings.can_edit" class="rounded-lg bg-surface-gray-1 p-3 text-xs text-ink-gray-6">
          You can see these settings but only a System Manager may change them.
        </div>
        <div v-else class="flex justify-end">
          <Button variant="solid" :loading="saving" label="Save settings" @click="save" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Button, FormControl, ErrorMessage, call } from 'frappe-ui'
import Skeleton from '@/components/Skeleton.vue'
import LinkField from '@/components/LinkField.vue'

const loading = ref(false)
const saving = ref(false)
const error = ref('')
const notice = ref(null)
const settings = ref({ exists: false, can_edit: false })

const form = reactive({
  payment_approver: '',
  payment_approver_email: '',
  payment_approver_phone: '',
  notify_by_email: true,
  notify_by_whatsapp: false,
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await call('kamil.masters.get_kamil_settings')
    settings.value = res || { exists: false, can_edit: false }
    Object.assign(form, {
      payment_approver: res?.payment_approver || '',
      payment_approver_email: res?.payment_approver_email || '',
      payment_approver_phone: res?.payment_approver_phone || '',
      notify_by_email: res?.notify_by_email !== 0,
      notify_by_whatsapp: !!res?.notify_by_whatsapp,
    })
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not load the settings.'
  } finally {
    loading.value = false
  }
}
onMounted(load)

/** Picking a user fills the email in, unless one was typed by hand. */
async function onApproverChange(value) {
  form.payment_approver = value || ''
  if (!value || form.payment_approver_email) return
  try {
    const user = await call('kamil.masters.get_user', { name: value })
    form.payment_approver_email = user?.email || ''
  } catch (e) {
    /* the email can still be typed in */
  }
}

async function save() {
  saving.value = true
  error.value = ''
  notice.value = null
  try {
    const res = await call('kamil.masters.save_kamil_settings', {
      values: JSON.stringify({
        payment_approver: form.payment_approver || null,
        payment_approver_email: form.payment_approver_email || null,
        payment_approver_phone: form.payment_approver_phone || null,
        notify_by_email: form.notify_by_email ? 1 : 0,
        notify_by_whatsapp: form.notify_by_whatsapp ? 1 : 0,
      }),
    })
    settings.value = res || settings.value
    notice.value = { ok: true, text: 'Settings saved.' }
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not save the settings.'
  } finally {
    saving.value = false
  }
}
</script>
