<template>
  <div class="mx-auto flex w-full min-h-0 max-w-5xl flex-1 flex-col gap-3 p-3 md:p-5">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h2 class="text-lg font-semibold text-ink-gray-8">Chart of Accounts</h2>
      <div class="flex flex-wrap items-center gap-2">
        <TextInput
          class="w-full sm:w-56"
          type="text"
          :modelValue="search"
          placeholder="Search accounts…"
          @update:modelValue="(v) => (search = v ?? '')"
        />
        <Button :label="showDisabled ? 'Hiding none' : 'Show disabled'" @click="toggleDisabled" />
        <Button v-if="canCreate" variant="solid" label="New Account" @click="openNew()">
          <template #prefix><Plus class="h-4 w-4" /></template>
        </Button>
      </div>
    </div>

    <Tabs class="!flex-none" v-model="tab" :tabs="tabs" />

    <div v-if="loading" class="space-y-2">
      <Skeleton v-for="n in 10" :key="n" class="h-8 w-full" />
    </div>
    <div v-else-if="error" class="rounded-lg border border-outline-gray-1 bg-surface-white p-6 text-center text-sm text-red-600">
      {{ error }}
    </div>

    <!-- Tree -->
    <div v-else-if="tab === 0" class="min-h-0 flex-1 overflow-auto rounded-lg border border-outline-gray-1 bg-surface-white p-2">
      <p v-if="!tree.length" class="p-6 text-center text-sm text-ink-gray-5">No accounts found.</p>
      <AccountNode
        v-for="node in tree"
        :key="node.name"
        :node="node"
        :depth="0"
        :expanded="expanded"
        :balances="balances"
        :currency="currency"
        :can-write="canWrite"
        :can-create="canCreate"
        @toggle="toggleNode"
        @edit="openEdit"
        @add-child="openNew"
      />
    </div>

    <!-- Flat list -->
    <div v-else class="min-h-0 flex-1 overflow-auto rounded-lg border border-outline-gray-1 bg-surface-white">
      <table class="w-full text-sm">
        <thead class="sticky top-0 z-10 bg-surface-gray-2">
          <tr class="text-left text-xs font-medium text-ink-gray-5">
            <th class="px-3 py-2">Account</th>
            <th class="px-3 py-2">Number</th>
            <th class="px-3 py-2">Root</th>
            <th class="px-3 py-2">Type</th>
            <th class="px-3 py-2 text-right">Balance</th>
            <th class="px-3 py-2"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in filteredFlat" :key="a.name" class="border-t border-outline-gray-1">
            <td class="px-3 py-1.5">
              <span :class="a.is_group ? 'font-medium text-ink-gray-8' : 'text-ink-gray-7'">{{ a.account_name }}</span>
              <Badge v-if="a.disabled" class="ml-2" theme="red" label="Disabled" />
              <Badge v-else-if="a.is_group" class="ml-2" theme="gray" label="Group" />
            </td>
            <td class="px-3 py-1.5 text-ink-gray-6">{{ a.account_number || '' }}</td>
            <td class="px-3 py-1.5">
              <Badge v-if="a.root_type" :theme="rootTheme(a.root_type)" :label="a.root_type" />
            </td>
            <td class="px-3 py-1.5 text-ink-gray-6">{{ a.account_type || '' }}</td>
            <td class="px-3 py-1.5 text-right tabular-nums text-ink-gray-7">
              {{ balances[a.name] !== undefined ? money(balances[a.name]) : '' }}
            </td>
            <td class="px-3 py-1.5 text-right">
              <Button v-if="canWrite" label="Edit" @click="openEdit(a)" />
            </td>
          </tr>
          <tr v-if="!filteredFlat.length">
            <td colspan="6" class="p-8 text-center text-sm text-ink-gray-5">No accounts match.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <AccountDialog v-model="showDialog" :account="editing" :parent-default="parentDefault" @saved="onSaved" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Button, Badge, TextInput, Tabs, call } from 'frappe-ui'
import Plus from '~icons/lucide/plus'
import ListIcon from '~icons/lucide/list'
import Network from '~icons/lucide/network'
import Skeleton from '@/components/Skeleton.vue'
import AccountNode from '@/components/AccountNode.vue'
import AccountDialog from '@/components/dialogs/AccountDialog.vue'
import { defaultCurrency } from '@/utils/money.js'

const tabs = [
  { label: 'Tree', icon: Network },
  { label: 'List', icon: ListIcon },
]
const tab = ref(0)

const loading = ref(false)
const error = ref('')
const tree = ref([])
const flat = ref([])
const balances = ref({})
const currency = ref('')
const canCreate = ref(false)
const canWrite = ref(false)
const showDisabled = ref(false)
const search = ref('')

const expanded = ref(new Set())
const showDialog = ref(false)
const editing = ref(null)
const parentDefault = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await call('kamil.masters.get_chart_of_accounts', {
      include_disabled: showDisabled.value ? 1 : 0,
    })
    tree.value = res?.tree || []
    flat.value = res?.flat || []
    canCreate.value = !!res?.can_create
    canWrite.value = !!res?.can_write
    // Start with the roots open — a fully collapsed chart tells you nothing.
    expanded.value = new Set(tree.value.map((n) => n.name))
    try {
      balances.value = (await call('kamil.masters.get_account_balances')) || {}
    } catch (e) {
      balances.value = {}
    }
  } catch (e) {
    error.value = e?.messages?.join(', ') || e?.message || 'Could not load the chart of accounts.'
    tree.value = []
    flat.value = []
  } finally {
    loading.value = false
  }
}
onMounted(load)

function toggleDisabled() {
  showDisabled.value = !showDisabled.value
  load()
}
function toggleNode(name) {
  const next = new Set(expanded.value)
  if (next.has(name)) next.delete(name)
  else next.add(name)
  expanded.value = next
}

const filteredFlat = computed(() => {
  const q = search.value.trim().toLowerCase()
  const rows = [...flat.value].sort((a, b) => (a.account_name || '').localeCompare(b.account_name || ''))
  if (!q) return rows
  return rows.filter(
    (a) =>
      (a.account_name || '').toLowerCase().includes(q) ||
      (a.account_number || '').toLowerCase().includes(q) ||
      (a.account_type || '').toLowerCase().includes(q),
  )
})

function openNew(parent) {
  editing.value = null
  parentDefault.value = typeof parent === 'string' ? parent : parent?.name || ''
  showDialog.value = true
}
function openEdit(account) {
  editing.value = account
  parentDefault.value = ''
  showDialog.value = true
}
function onSaved() {
  load()
}

const ROOT_THEME = { Asset: 'blue', Liability: 'orange', Equity: 'green', Income: 'green', Expense: 'red' }
function rootTheme(root) {
  return ROOT_THEME[root] || 'gray'
}
function money(v) {
  if (v === null || v === undefined) return ''
  try {
    return new Intl.NumberFormat('en-KE', { style: 'currency', currency: currency.value || defaultCurrency(), maximumFractionDigits: 0 }).format(v)
  } catch {
    return v
  }
}
</script>
