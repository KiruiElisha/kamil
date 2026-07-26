<template>
  <div class="mx-auto w-full min-h-0 max-w-2xl flex-1 overflow-auto p-3 md:p-5">
    <h2 class="text-lg font-semibold text-ink-gray-8">My Email Account</h2>
    <p class="mt-1 text-sm text-ink-gray-5">
      Set up your own mailbox so mail the app sends on your behalf comes from your address.
      Your password is handed straight to Frappe, which stores it encrypted.
    </p>

    <div v-if="loading" class="mt-4 space-y-2">
      <Skeleton v-for="n in 6" :key="n" class="h-10 w-full" />
    </div>

    <div v-else class="mt-4 space-y-4">
      <div
        v-if="account.exists"
        class="flex flex-wrap items-center gap-2 rounded-lg border border-outline-gray-1 bg-surface-gray-1 p-3 text-sm"
      >
        <Badge theme="green" label="Configured" />
        <span class="text-ink-gray-7">{{ account.email_id }}</span>
        <Badge v-if="account.awaiting_password" theme="orange" label="Awaiting password" />
        <Badge v-if="account.enable_outgoing" theme="blue" label="Sending" />
        <Badge v-if="account.enable_incoming" theme="blue" label="Receiving" />
      </div>

      <div class="space-y-3 rounded-xl border border-outline-gray-1 bg-surface-white p-4">
        <div>
          <label class="mb-1 block text-xs text-ink-gray-5">Email address</label>
          <div class="rounded-lg border border-outline-gray-2 bg-surface-gray-2 px-3 py-2 text-sm text-ink-gray-7">
            {{ myAddress || '—' }}
          </div>
          <p class="mt-1 text-xs text-ink-gray-5">
            This is your own account's address and cannot be changed here — it is what ties the
            mailbox to you.
          </p>
        </div>
        <FormControl
          type="password"
          :label="account.exists ? 'Password (leave blank to keep the current one)' : 'Password / app password'"
          v-model="form.password"
        />
        <p class="text-xs text-ink-gray-5">
          For Gmail and Microsoft 365 this must be an app password, not your normal sign-in password.
        </p>

        <!-- Outgoing -->
        <div class="border-t border-outline-gray-1 pt-3">
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium text-ink-gray-8">Sending (SMTP)</span>
            <FormControl type="checkbox" label="Enabled" v-model="form.enable_outgoing" />
          </div>
          <div v-if="form.enable_outgoing" class="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <FormControl type="text" label="SMTP server" placeholder="smtp.gmail.com" v-model="form.smtp_server" />
            <FormControl type="number" label="Port" placeholder="587" v-model="form.smtp_port" />
            <FormControl type="checkbox" label="Use TLS" v-model="form.use_tls" />
            <FormControl type="checkbox" label="Use SSL" v-model="form.use_ssl_for_outgoing" />
          </div>
        </div>

        <!-- Incoming -->
        <div class="border-t border-outline-gray-1 pt-3">
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium text-ink-gray-8">Receiving (IMAP/POP)</span>
            <FormControl type="checkbox" label="Enabled" v-model="form.enable_incoming" />
          </div>
          <div v-if="form.enable_incoming" class="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <FormControl type="text" label="Mail server" placeholder="imap.gmail.com" v-model="form.email_server" />
            <FormControl type="checkbox" label="Use IMAP" v-model="form.use_imap" />
            <FormControl type="checkbox" label="Use SSL" v-model="form.use_ssl" />
          </div>
        </div>

        <div v-if="notice" class="rounded-lg border p-3 text-sm" :class="notice.ok ? 'border-green-200 bg-green-50 text-green-700' : 'border-red-200 bg-red-50 text-red-700'">
          {{ notice.text }}
        </div>
        <ErrorMessage :message="error" />

        <div class="flex flex-wrap justify-end gap-2">
          <Button v-if="account.exists" theme="red" label="Remove" :loading="removing" @click="remove" />
          <Button variant="solid" :loading="saving" :label="account.exists ? 'Save changes' : 'Set up email'" @click="save" />
        </div>
      </div>

      <p class="text-xs text-ink-gray-5">
        Frappe verifies the connection when you save, so an incorrect server or password will be
        reported here rather than failing silently later.
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Button, Badge, FormControl, ErrorMessage, call } from 'frappe-ui'
import Skeleton from '@/components/Skeleton.vue'

const loading = ref(false)
const saving = ref(false)
const removing = ref(false)
const error = ref('')
const notice = ref(null)
const account = ref({ exists: false })
// Pinned server-side to the signed-in user's address; shown, never edited.
const myAddress = ref('')

const form = reactive({
  password: '',
  enable_outgoing: true,
  smtp_server: '',
  smtp_port: 587,
  use_tls: true,
  use_ssl_for_outgoing: false,
  enable_incoming: false,
  email_server: '',
  use_imap: true,
  use_ssl: true,
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await call('kamil.masters.get_my_email_account')
    account.value = res || { exists: false }
    myAddress.value = res?.email_id || ''
    if (res?.exists) {
      Object.assign(form, {
        password: '',
        enable_outgoing: !!res.enable_outgoing,
        smtp_server: res.smtp_server || '',
        smtp_port: res.smtp_port || 587,
        use_tls: !!res.use_tls,
        use_ssl_for_outgoing: !!res.use_ssl_for_outgoing,
        enable_incoming: !!res.enable_incoming,
        email_server: res.email_server || '',
        use_imap: !!res.use_imap,
        use_ssl: !!res.use_ssl,
      })
    }
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not load your email settings.'
  } finally {
    loading.value = false
  }
}
onMounted(load)

async function save() {
  error.value = ''
  notice.value = null
  if (!myAddress.value) {
    error.value = 'Your user account has no email address to set up.'
    return
  }
  if (!account.value.exists && !form.password) {
    error.value = 'Enter the password for this mailbox.'
    return
  }

  saving.value = true
  try {
    const values = {
      enable_outgoing: form.enable_outgoing ? 1 : 0,
      smtp_server: form.smtp_server.trim(),
      smtp_port: form.smtp_port || null,
      use_tls: form.use_tls ? 1 : 0,
      use_ssl_for_outgoing: form.use_ssl_for_outgoing ? 1 : 0,
      enable_incoming: form.enable_incoming ? 1 : 0,
      email_server: form.email_server.trim(),
      use_imap: form.use_imap ? 1 : 0,
      use_ssl: form.use_ssl ? 1 : 0,
    }
    // Only send a password when one was actually typed, so saving other changes
    // does not wipe the stored credential.
    if (form.password) values.password = form.password

    await call('kamil.masters.save_my_email_account', { values: JSON.stringify(values) })
    form.password = ''
    notice.value = { ok: true, text: 'Email account saved.' }
    await load()
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not save your email settings.'
  } finally {
    saving.value = false
  }
}

async function remove() {
  removing.value = true
  error.value = ''
  notice.value = null
  try {
    await call('kamil.masters.delete_my_email_account')
    notice.value = { ok: true, text: 'Email account removed.' }
    account.value = { exists: false }
    Object.assign(form, { password: '', smtp_server: '', email_server: '' })
    await load()
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not remove your email account.'
  } finally {
    removing.value = false
  }
}
</script>
