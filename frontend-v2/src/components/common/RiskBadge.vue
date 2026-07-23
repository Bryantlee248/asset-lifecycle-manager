<script setup lang="ts">
import { computed } from 'vue'

// RiskBadge — semantic risk coloring.
//   'critical' (严重) -> red, 'warning' (中警) -> orange, 'caution' (注意) -> yellow, 'ok' -> green
const props = defineProps<{
  level: 'critical' | 'warning' | 'caution' | 'ok'
  label?: string
  dot?: boolean
}>()

const meta = computed(() => {
  switch (props.level) {
    case 'critical':
      return { fg: 'var(--risk-critical)', bg: '#fde8e8', text: props.label || '严重' }
    case 'warning':
      return { fg: 'var(--risk-warning)', bg: '#fff7e8', text: props.label || '中等' }
    case 'caution':
      return { fg: 'var(--risk-caution)', bg: '#fef9ec', text: props.label || '注意' }
    case 'ok':
    default:
      return { fg: 'var(--risk-ok)', bg: '#e8f8f0', text: props.label || '正常' }
  }
})
</script>

<template>
  <span
    class="inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-xs font-medium"
    :style="{ background: meta.bg, color: meta.fg }"
  >
    <span
      v-if="dot"
      class="inline-block h-1.5 w-1.5 rounded-full"
      :style="{ background: meta.fg }"
    ></span>
    {{ meta.text }}
  </span>
</template>
