<template>
  <div>
    <div
      class="group flex items-center gap-1.5 rounded px-1 py-1 hover:bg-surface-gray-2"
      :style="{ paddingLeft: depth * 16 + 4 + 'px' }"
    >
      <!-- Twisty, or a spacer to keep leaf labels aligned with their siblings -->
      <button
        v-if="hasChildren"
        class="flex h-5 w-5 shrink-0 items-center justify-center rounded text-ink-gray-6 hover:bg-surface-gray-3"
        :aria-label="isOpen ? 'Collapse' : 'Expand'"
        @click="emit('toggle', node.name)"
      >
        <ChevronRight class="h-4 w-4 transition-transform" :class="isOpen ? 'rotate-90' : ''" />
      </button>
      <span v-else class="h-5 w-5 shrink-0" />

      <component :is="hasChildren ? Folder : FileText" class="h-4 w-4 shrink-0 text-ink-gray-5" />

      <span class="min-w-0 flex-1 truncate text-sm" :class="node.is_group ? 'font-medium text-ink-gray-8' : 'text-ink-gray-7'">
        <span v-if="node.account_number" class="text-ink-gray-5">{{ node.account_number }} · </span>{{ node.account_name }}
      </span>

      <Badge v-if="node.disabled" theme="red" label="Disabled" />
      <Badge v-if="node.account_type" theme="gray" :label="node.account_type" />

      <span v-if="balance !== undefined" class="shrink-0 tabular-nums text-xs text-ink-gray-6">
        {{ money(balance) }}
      </span>

      <!-- Actions stay hidden until hover so the tree reads cleanly -->
      <span class="flex shrink-0 gap-1 opacity-0 transition-opacity group-hover:opacity-100">
        <button
          v-if="canCreate && node.is_group"
          class="rounded px-1.5 py-0.5 text-xs text-ink-gray-6 hover:bg-surface-gray-3"
          @click="emit('add-child', node.name)"
        >
          Add
        </button>
        <button
          v-if="canWrite"
          class="rounded px-1.5 py-0.5 text-xs text-ink-gray-6 hover:bg-surface-gray-3"
          @click="emit('edit', node)"
        >
          Edit
        </button>
      </span>
    </div>

    <template v-if="hasChildren && isOpen">
      <AccountNode
        v-for="child in node.children"
        :key="child.name"
        :node="child"
        :depth="depth + 1"
        :expanded="expanded"
        :balances="balances"
        :currency="currency"
        :can-write="canWrite"
        :can-create="canCreate"
        @toggle="(n) => emit('toggle', n)"
        @edit="(n) => emit('edit', n)"
        @add-child="(n) => emit('add-child', n)"
      />
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Badge } from 'frappe-ui'
import ChevronRight from '~icons/lucide/chevron-right'
import Folder from '~icons/lucide/folder'
import FileText from '~icons/lucide/file-text'

const props = defineProps({
  node: { type: Object, required: true },
  depth: { type: Number, default: 0 },
  expanded: { type: Set, required: true },
  balances: { type: Object, default: () => ({}) },
  currency: { type: String, default: 'KES' },
  canWrite: { type: Boolean, default: false },
  canCreate: { type: Boolean, default: false },
})
const emit = defineEmits(['toggle', 'edit', 'add-child'])

const hasChildren = computed(() => (props.node.children || []).length > 0)
const isOpen = computed(() => props.expanded.has(props.node.name))
const balance = computed(() => props.balances[props.node.name])

function money(v) {
  if (v === null || v === undefined) return ''
  try {
    return new Intl.NumberFormat('en-KE', { style: 'currency', currency: props.currency || 'KES', maximumFractionDigits: 0 }).format(v)
  } catch {
    return v
  }
}
</script>
