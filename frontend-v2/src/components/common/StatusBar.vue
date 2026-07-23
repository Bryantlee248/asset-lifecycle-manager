<script setup lang="ts">
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()
</script>

<template>
  <footer
    class="flex h-7 items-center gap-3 border-t border-[var(--border)] bg-[var(--surface)] px-4 text-xs text-slate-500"
  >
    <span class="flex items-center gap-1.5">
      <span
        class="inline-block h-1.5 w-1.5 rounded-full"
        :class="ui.globalLoading ? 'bg-[var(--risk-caution)] animate-pulse' : 'bg-[var(--risk-ok)]'"
      ></span>
      {{ ui.globalLoading ? '正在加载…' : '就绪' }}
    </span>
    <span v-if="ui.errorMsg" class="truncate text-[var(--risk-critical)]" :title="ui.errorMsg">
      错误：{{ ui.errorMsg }}
    </span>
    <span class="ml-auto">C2 · 指挥台</span>
    <slot />
  </footer>
</template>
