<script setup lang="ts">
// Vertical lifecycle/audit timeline. Pure presentational — receives events and
// renders a colored node per event. Used by AssetDetailWorkbench and the
// lifecycle module detail workbenches.

const props = defineProps<{
  events?: {
    time?: string
    title: string
    desc?: string
    tone?: 'brand' | 'ok' | 'warning' | 'critical' | 'neutral'
  }[]
}>()

const toneColor: Record<string, string> = {
  brand: 'var(--brand)',
  ok: 'var(--risk-ok)',
  warning: 'var(--risk-warning)',
  critical: 'var(--risk-critical)',
  neutral: '#94a3b8',
}
</script>

<template>
  <ol class="relative space-y-3 border-l border-[var(--border)] pl-4">
    <li v-for="(e, i) in events || []" :key="i" class="relative">
      <span
        class="absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full ring-2 ring-white"
        :style="{ background: toneColor[e.tone || 'neutral'] }"
      ></span>
      <div class="flex flex-wrap items-baseline gap-2">
        <span v-if="e.time" class="text-xs text-slate-400">{{ e.time }}</span>
        <span class="text-sm font-medium text-slate-800">{{ e.title }}</span>
      </div>
      <p v-if="e.desc" class="mt-0.5 text-xs text-slate-500">{{ e.desc }}</p>
    </li>
    <li v-if="!(events && events.length)" class="text-xs text-slate-400">暂无时间线记录</li>
  </ol>
</template>
