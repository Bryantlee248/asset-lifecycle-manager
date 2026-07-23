<script setup lang="ts">
// TaskCenter — local task board for import / export operations. Tasks are
// frontend-only state records (status: uploading | validating | running |
// success | failed); the actual API calls are performed by the host page
// (ImportExportPage) via the emitted download / retry / remove events.
// Failure detail is shown via the `errorLines` array.

import { computed } from 'vue'
import RiskBadge from '@/components/common/RiskBadge.vue'
import { Download, RotateCw, Trash2 } from 'lucide-vue-next'

export interface ImportExportTask {
  id: string | number
  name: string
  status: 'uploading' | 'validating' | 'running' | 'success' | 'failed'
  detail?: string
  errorLines?: string[]
}

const props = defineProps<{
  tasks: ImportExportTask[]
}>()

const emit = defineEmits<{
  (e: 'download', id: string | number): void
  (e: 'retry', id: string | number): void
  (e: 'remove', id: string | number): void
}>()

function statusMeta(s: string): { level: 'critical' | 'warning' | 'caution' | 'ok'; label: string } {
  switch (s) {
    case 'uploading':
      return { level: 'caution', label: '上传中' }
    case 'validating':
      return { level: 'caution', label: '校验中' }
    case 'running':
      return { level: 'warning', label: '处理中' }
    case 'success':
      return { level: 'ok', label: '成功' }
    case 'failed':
      return { level: 'critical', label: '失败' }
    default:
      return { level: 'caution', label: s }
  }
}
</script>

<template>
  <div class="space-y-2">
    <div v-if="!tasks.length" class="c2-panel px-3 py-10 text-center text-sm text-slate-400">暂无任务</div>
    <div
      v-for="task in tasks"
      :key="task.id"
      class="c2-panel flex flex-wrap items-center gap-3 px-4 py-3"
      :data-status="task.status"
    >
      <RiskBadge :level="statusMeta(task.status).level" :label="statusMeta(task.status).label" />
      <div class="min-w-0 flex-1">
        <p class="truncate text-sm font-medium text-slate-800">{{ task.name }}</p>
        <p v-if="task.detail && task.status !== 'failed'" class="truncate text-xs text-slate-400">{{ task.detail }}</p>
        <ul v-if="task.status === 'failed' && task.errorLines && task.errorLines.length" class="mt-1 space-y-0.5">
          <li v-for="(line, i) in task.errorLines" :key="i" class="text-xs text-[var(--risk-critical)]">{{ line }}</li>
        </ul>
      </div>
      <div class="flex items-center gap-2">
        <button
          v-if="task.status === 'success'"
          class="c2-btn c2-btn-ghost px-2 py-1 text-xs"
          type="button"
          @click="emit('download', task.id)"
        >
          <Download :size="13" /> 下载
        </button>
        <button
          v-if="task.status === 'failed'"
          class="c2-btn c2-btn-ghost px-2 py-1 text-xs"
          type="button"
          @click="emit('retry', task.id)"
        >
          <RotateCw :size="13" /> 重试
        </button>
        <button
          class="c2-btn c2-btn-ghost px-2 py-1 text-xs text-slate-400"
          type="button"
          @click="emit('remove', task.id)"
        >
          <Trash2 :size="13" /> 移除
        </button>
      </div>
    </div>
  </div>
</template>
