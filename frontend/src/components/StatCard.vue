<template>
  <div class="rounded-xl border border-outline-gray-1 bg-surface-white p-4">
    <div class="flex h-9 w-9 items-center justify-center rounded-lg" :class="chip">
      <component :is="iconComponent" class="h-5 w-5" />
    </div>
    <div
      class="mt-3 truncate font-semibold text-ink-gray-9"
      :class="small ? 'text-base' : 'text-xl'"
      :title="String(value ?? '')"
    >
      {{ value }}
    </div>
    <div class="truncate text-sm text-ink-gray-5" :title="label">{{ label }}</div>
    <div v-if="sub" class="mt-0.5 truncate text-xs text-ink-gray-4">{{ sub }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { iconFor } from '@/utils/icons.js'

const props = defineProps({
  label: { type: String, default: '' },
  value: { type: [String, Number], default: '' },
  // Either a lucide component or one of the names in utils/icons.js
  icon: { type: [Object, Function, String], default: '' },
  color: { type: String, default: 'blue' },
  sub: { type: String, default: '' },
  small: { type: Boolean, default: false },
})

// The dashboard's chip palette — one place, so every card in the app matches.
const CHIP = {
  green: 'bg-green-100 text-green-600',
  blue: 'bg-blue-100 text-blue-600',
  amber: 'bg-amber-100 text-amber-600',
  orange: 'bg-orange-100 text-orange-600',
  red: 'bg-red-100 text-red-600',
  violet: 'bg-violet-100 text-violet-600',
  gray: 'bg-surface-gray-3 text-ink-gray-7',
}

const chip = computed(() => CHIP[props.color] || CHIP.blue)
const iconComponent = computed(() => iconFor(props.icon))
</script>
