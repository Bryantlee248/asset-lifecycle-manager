<script setup lang="ts">
// On-demand ECharts wrapper — only register the chart types/components that are
// actually used across the app (Bar / Line / Pie + grid/tooltip/legend/title +
// canvas renderer). This keeps the echarts vendor chunk small and lets
// vite manualChunks split it out of the main entry. Props (option/height) and
// render behaviour are unchanged from the full-import version.
import { ref, onMounted, onBeforeUnmount, watch, shallowRef } from 'vue'
import { use, init } from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([
  BarChart,
  LineChart,
  PieChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  CanvasRenderer,
])

const props = defineProps<{
  option: Record<string, any>
  height?: string
}>()

const el = ref<HTMLDivElement | null>(null)
const chart = shallowRef<ReturnType<typeof init> | null>(null)

function render() {
  if (!chart.value) return
  chart.value.setOption(props.option, true)
}

function resize() {
  chart.value?.resize()
}

onMounted(() => {
  if (!el.value) return
  chart.value = init(el.value)
  render()
  window.addEventListener('resize', resize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart.value?.dispose()
  chart.value = null
})

watch(() => props.option, render, { deep: true })
</script>

<template>
  <div ref="el" :style="{ width: '100%', height: height || '280px' }"></div>
</template>
