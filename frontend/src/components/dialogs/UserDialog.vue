<template>
  <Dialog v-model="show" :options="{ title: isEdit ? `Edit ${userName}` : 'New User', size: '2xl' }">
    <template #body-content>
      <div v-if="loading" class="p-6 text-center text-sm text-ink-gray-5">Loading…</div>
      <div v-else class="space-y-3">
        <FormControl v-if="!isEdit" type="text" label="Email" placeholder="person@company.com" v-model="form.email" />
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <FormControl type="text" label="First Name" v-model="form.first_name" />
          <FormControl type="text" label="Last Name" v-model="form.last_name" />
        </div>
        <FormControl type="text" label="Mobile Number" v-model="form.mobile_no" />

        <div class="flex flex-wrap gap-4">
          <FormControl type="checkbox" label="Enabled" v-model="form.enabled" />
        </div>

        <div>
          <div class="mb-1 flex items-center justify-between">
            <label class="text-xs text-ink-gray-5">Roles</label>
            <span class="text-xs text-ink-gray-5">{{ form.roles.length }} selected</span>
          </div>
          <div class="max-h-56 overflow-y-auto rounded-lg border border-outline-gray-1 p-2">
            <label
              v-for="r in roleOptions"
              :key="r.value"
              class="flex cursor-pointer items-center gap-2 rounded px-1.5 py-1 text-sm hover:bg-surface-gray-2"
            >
              <input type="checkbox" :value="r.value" :checked="form.roles.includes(r.value)" @change="toggleRole(r.value)" />
              <span class="text-ink-gray-7">{{ r.label }}</span>
            </label>
            <p v-if="!roleOptions.length" class="p-2 text-xs text-ink-gray-5">No assignable roles available.</p>
          </div>
        </div>

        <p v-if="!isEdit" class="text-xs text-ink-gray-5">
          Frappe sends the welcome and password-setup email itself — no password is entered here.
        </p>

        <ErrorMessage :message="error" />
      </div>
    </template>
    <template #actions="{ close }">
      <div class="flex w-full justify-end gap-2">
        <Button label="Cancel" @click="close" />
        <Button variant="solid" :loading="saving" :label="isEdit ? 'Save' : 'Create user'" @click="save" />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { Dialog, Button, FormControl, ErrorMessage, call } from 'frappe-ui'

const show = defineModel()
const props = defineProps({ userName: { type: String, default: '' } })
const emit = defineEmits(['saved'])

const isEdit = computed(() => !!props.userName)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const roleOptions = ref([])

const form = reactive({
  email: '',
  first_name: '',
  last_name: '',
  mobile_no: '',
  enabled: true,
  roles: [],
})

function resetForm() {
  Object.assign(form, { email: '', first_name: '', last_name: '', mobile_no: '', enabled: true, roles: [] })
}

watch(show, async (v) => {
  if (!v) return
  error.value = ''
  resetForm()

  loading.value = true
  try {
    roleOptions.value = (await call('kamil.masters.list_assignable_roles')) || []
    if (isEdit.value) {
      const u = await call('kamil.masters.get_user', { name: props.userName })
      Object.assign(form, {
        email: u.email || u.name,
        first_name: u.first_name || '',
        last_name: u.last_name || '',
        mobile_no: u.mobile_no || '',
        enabled: !!u.enabled,
        roles: u.roles || [],
      })
    }
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not load this user.'
  } finally {
    loading.value = false
  }
})

function toggleRole(role) {
  const i = form.roles.indexOf(role)
  if (i === -1) form.roles.push(role)
  else form.roles.splice(i, 1)
}

async function save() {
  error.value = ''
  if (!isEdit.value && !form.email.trim()) {
    error.value = 'Email is required.'
    return
  }

  saving.value = true
  try {
    await call('kamil.masters.save_user', {
      values: JSON.stringify({
        name: isEdit.value ? props.userName : null,
        email: form.email.trim(),
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        mobile_no: form.mobile_no.trim(),
        enabled: form.enabled ? 1 : 0,
        roles: form.roles,
      }),
    })
    show.value = false
    emit('saved')
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not save this user.'
  } finally {
    saving.value = false
  }
}
</script>
