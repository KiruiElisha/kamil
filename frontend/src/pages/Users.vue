<template>
  <div class="mx-auto flex w-full min-h-0 max-w-4xl flex-1 flex-col gap-3 p-3 md:p-5">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h2 class="text-lg font-semibold text-ink-gray-8">Users</h2>
      <div class="flex flex-wrap items-center gap-2">
        <TextInput
          class="w-full sm:w-56"
          type="text"
          :modelValue="search"
          placeholder="Search users…"
          @update:modelValue="onSearch"
        />
        <Button v-if="canCreate" variant="solid" label="New User" @click="openNew">
          <template #prefix><Plus class="h-4 w-4" /></template>
        </Button>
      </div>
    </div>

    <div v-if="loading" class="space-y-2">
      <Skeleton v-for="n in 8" :key="n" class="h-10 w-full" />
    </div>
    <div v-else-if="error" class="rounded-lg border border-outline-gray-1 bg-surface-white p-6 text-center text-sm text-red-600">
      {{ error }}
    </div>
    <div v-else class="min-h-0 flex-1 overflow-auto rounded-lg border border-outline-gray-1 bg-surface-white">
      <div v-if="!users.length" class="p-8 text-center text-sm text-ink-gray-5">No users found.</div>
      <div
        v-for="u in users"
        :key="u.name"
        class="flex items-center gap-3 border-b border-outline-gray-1 px-3 py-2.5 last:border-0"
      >
        <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-gray-3 text-xs font-semibold text-ink-gray-7">
          {{ initials(u.full_name) }}
        </span>
        <div class="min-w-0 flex-1">
          <div class="truncate text-sm font-medium text-ink-gray-8">{{ u.full_name }}</div>
          <div class="truncate text-xs text-ink-gray-5">{{ u.email }}</div>
        </div>
        <Badge :theme="u.enabled ? 'green' : 'red'" :label="u.enabled ? 'Enabled' : 'Disabled'" />
        <Badge v-if="u.user_type !== 'System User'" theme="gray" :label="u.user_type" />
        <div class="flex shrink-0 gap-1">
          <Button v-if="canWrite" label="Edit" @click="openEdit(u)" />
          <Button
            v-if="canWrite && u.name !== 'Administrator'"
            :label="u.enabled ? 'Disable' : 'Enable'"
            :theme="u.enabled ? 'red' : 'gray'"
            :loading="toggling === u.name"
            @click="toggleEnabled(u)"
          />
        </div>
      </div>
    </div>

    <UserDialog v-model="showDialog" :user-name="editingName" @saved="load" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Button, Badge, TextInput, call, debounce } from 'frappe-ui'
import Plus from '~icons/lucide/plus'
import Skeleton from '@/components/Skeleton.vue'
import UserDialog from '@/components/dialogs/UserDialog.vue'

const users = ref([])
const loading = ref(false)
const error = ref('')
const search = ref('')
const canCreate = ref(false)
const canWrite = ref(false)
const toggling = ref('')

const showDialog = ref(false)
const editingName = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await call('kamil.masters.list_users', { search: search.value || '' })
    users.value = res?.users || []
    canCreate.value = !!res?.can_create
    canWrite.value = !!res?.can_write
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not load users.'
    users.value = []
  } finally {
    loading.value = false
  }
}
onMounted(load)

const debouncedLoad = debounce(load, 350)
function onSearch(v) {
  search.value = v ?? ''
  debouncedLoad()
}

function openNew() {
  editingName.value = ''
  showDialog.value = true
}
function openEdit(u) {
  editingName.value = u.name
  showDialog.value = true
}

async function toggleEnabled(u) {
  toggling.value = u.name
  error.value = ''
  try {
    await call('kamil.masters.set_user_enabled', { name: u.name, enabled: u.enabled ? 0 : 1 })
    await load()
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not change that user.'
  } finally {
    toggling.value = ''
  }
}

function initials(name) {
  return (name || '?')
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0])
    .join('')
    .toUpperCase()
}
</script>
