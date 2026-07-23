<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  stage: string
  size?: 'sm' | 'md'
}>()

// 7-stage semantic colors — identical semantics to legacy `.stage-*` classes.
const map: Record<string, { bg: string; fg: string }> = {
  规划: { bg: 'var(--stage-规划-bg)', fg: 'var(--stage-规划-fg)' },
  在途: { bg: 'var(--stage-在途-bg)', fg: 'var(--stage-在途-fg)' },
  上架: { bg: 'var(--stage-上架-bg)', fg: 'var(--stage-上架-fg)' },
  运行: { bg: 'var(--stage-运行-bg)', fg: 'var(--stage-运行-fg)' },
  维修: { bg: 'var(--stage-维修-bg)', fg: 'var(--stage-维修-fg)' },
  待报废: { bg: 'var(--stage-待报废-bg)', fg: 'var(--stage-待报废-fg)' },
  已报废: { bg: 'var(--stage-已报废-bg)', fg: 'var(--stage-已报废-fg)' },
}

const style = computed(() => {
  const c = map[props.stage] || { bg: 'var(--canvas)', fg: '#475569' }
  return { background: c.bg, color: c.fg }
})
</script>

<template>
  <span
    class="inline-flex items-center rounded font-medium"
    :class="size === 'sm' ? 'px-1.5 py-0.5 text-[11px]' : 'px-2 py-0.5 text-xs'"
    :style="style"
  >
    {{ stage }}
  </span>
</template>
