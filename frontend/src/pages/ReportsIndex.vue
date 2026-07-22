<template>
  <div class="mx-auto w-full min-h-0 max-w-6xl flex-1 space-y-4 overflow-auto p-3 md:p-5">
    <h2 class="text-lg font-semibold text-ink-gray-8">Reports</h2>
    <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <button
        v-for="r in REPORTS"
        :key="r.key"
        class="flex items-center gap-3 rounded-xl border border-outline-gray-1 bg-surface-white p-4 text-left transition-colors hover:border-outline-gray-3 active:bg-surface-gray-2"
        @click="open(r)"
      >
        <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-surface-gray-2 text-ink-gray-7">
          <component :is="r.icon" class="h-5 w-5" />
        </span>
        <span class="min-w-0">
          <span class="block truncate text-sm font-medium text-ink-gray-8">{{ r.title }}</span>
          <span class="block truncate text-xs text-ink-gray-5">{{ r.report }}</span>
        </span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { REPORTS } from '@/data/reports.js'
import { haptic } from '@/utils/haptics'

const router = useRouter()
function open(r) {
  haptic()
  router.push(`/report/${r.key}`)
}
</script>
