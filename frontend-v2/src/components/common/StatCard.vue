<script setup lang="ts">
defineProps<{
  label: string
  value: number | string
  hint?: string
  tone?: 'default' | 'risk' | 'brand' | 'caution'
  icon?: any
}>()
</script>

<template>
  <div class="c2-panel flex items-start gap-3 p-4">
    <span
      v-if="icon"
      class="flex h-9 w-9 shrink-0 items-center justify-center rounded"
      :class="{
        'bg-[#fde8e8] text-[var(--risk-critical)]': tone === 'risk',
        'bg-[#e8f8f0] text-[var(--brand)]': tone === 'brand',
        'bg-[#fef9ec] text-[var(--risk-caution)]': tone === 'caution',
        'bg-[var(--canvas)] text-slate-500': !tone || tone === 'default',
      }"
    >
      <component :is="icon" :size="18" />
    </span>
    <div class="min-w-0">
      <p class="truncate text-xs text-slate-500">{{ label }}</p>
      <p
        class="mt-0.5 text-2xl font-semibold"
        :class="{
          'text-[var(--risk-critical)]': tone === 'risk',
          'text-[var(--brand)]': tone === 'brand',
          'text-[var(--risk-caution)]': tone === 'caution',
          'text-slate-800': !tone || tone === 'default',
        }"
      >
        {{ value }}
      </p>
      <p v-if="hint" class="mt-0.5 truncate text-[11px] text-slate-400">{{ hint }}</p>
    </div>
  </div>
</template>
