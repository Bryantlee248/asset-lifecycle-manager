<script setup lang="ts">
import { Construction } from 'lucide-vue-next'

defineProps<{
  module: string
  description?: string
}>()
</script>

<template>
  <div class="mx-auto max-w-2xl">
    <div class="c2-panel flex flex-col items-center gap-3 px-6 py-16 text-center">
      <span class="flex h-14 w-14 items-center justify-center rounded-full bg-[var(--canvas)] text-[var(--brand)]">
        <Construction :size="26" />
      </span>
      <h2 class="text-lg font-semibold text-slate-800">{{ module }}</h2>
      <p class="text-sm text-slate-500">
        {{ description || '本模块将于后续批次交付。' }}
      </p>
      <span class="mt-1 rounded bg-[var(--canvas)] px-2 py-0.5 text-xs text-slate-400">建设中 · 批次二/三</span>
    </div>
  </div>
</template>
