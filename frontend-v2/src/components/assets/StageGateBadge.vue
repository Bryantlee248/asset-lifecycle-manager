<script setup lang="ts">
// Stage-gate result badge — surfaces whether a lifecycle stage transition is
// permitted by the backend gate (legacy onStageChange result.allowed).
const props = defineProps<{
  allowed?: boolean
  message?: string
}>()
</script>

<template>
  <span
    v-if="allowed"
    class="inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium"
    style="background: #e8f8f0; color: var(--risk-ok)"
  >
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
      <path d="M20 6 9 17l-5-5" />
    </svg>
    门禁通过，可流转
  </span>
  <span
    v-else
    class="inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium"
    style="background: #fde8e8; color: var(--risk-critical)"
  >
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
    门禁拦截<span v-if="message">：{{ message }}</span>
  </span>
</template>
