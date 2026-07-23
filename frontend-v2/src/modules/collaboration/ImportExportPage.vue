<script setup lang="ts">
// Import / Export task center — batch 3 collaboration page.
// Each operation (import / template download / export) spawns a local task
// record whose status walks uploading -> validating -> running -> success|failed.
// The underlying calls hit the SAME synchronous backend endpoints as the legacy
// frontend; no new backend task API is invented. Failures surface errorLines.
// Gate: import_export:export

import { ref } from 'vue'
import { RefreshCw, Upload, FileDown } from 'lucide-vue-next'
import TaskCenter from '@/components/collaboration/TaskCenter.vue'
import type { ImportExportTask } from '@/components/collaboration/TaskCenter.vue'
import { useUiStore } from '@/stores/ui'
import {
  importFile,
  downloadTemplate,
  exportAssets,
  exportByType,
  exportStats,
} from '@/services/importexport'

const ui = useUiStore()

const MODULE_TYPES = ['assets', 'procurement', 'inbound', 'outbound', 'change', 'fault', 'warranty', 'retirement']
const CATEGORIES = ['服务器', '网络设备', '安全设备', '存储设备', '终端设备']
const STAGES = ['规划', '在途', '上架', '运行', '维修', '待报废', '已报废']
const WARRANTY = ['在保', '临保', '已过保']

const importType = ref('assets')
const exportType = ref('procurement')
const fileInput = ref<HTMLInputElement | null>(null)

const assetFilter = ref<{ category: string; stage: string; warranty_status: string; search: string }>({
  category: '',
  stage: '',
  warranty_status: '',
  search: '',
})

const tasks = ref<(ImportExportTask & { op?: () => Promise<any> })[]>([])
let taskSeq = 0

function successText(res: any): string {
  if (res && typeof res === 'object' && 'success' in res) return `成功 ${res.success} 条`
  if (res instanceof Blob) return '文件已下载'
  return '操作完成'
}

function setStatus(id: number, patch: Partial<ImportExportTask>) {
  const t = tasks.value.find((x) => x.id === id)
  if (t) Object.assign(t, patch)
}

// Schedule the cosmetic status walk; guards ensure a finished task is never
// regressed by a late timer.
function schedule(id: number) {
  setTimeout(() => {
    const t = tasks.value.find((x) => x.id === id)
    if (t && t.status === 'uploading') t.status = 'validating'
  }, 150)
  setTimeout(() => {
    const t = tasks.value.find((x) => x.id === id)
    if (t && t.status === 'validating') t.status = 'running'
  }, 350)
}

async function runTask(name: string, op: () => Promise<any>) {
  const id = ++taskSeq
  tasks.value.unshift({ id, name, status: 'uploading', op })
  schedule(id)
  try {
    const res = await op()
    setStatus(id, { status: 'success', detail: successText(res) })
  } catch (e) {
    setStatus(id, { status: 'failed', errorLines: [(e as Error).message] })
  }
}

function onImport() {
  const file = fileInput.value?.files?.[0]
  if (!file) {
    ui.setError('请先选择 Excel 文件')
    return
  }
  const type = importType.value
  runTask(`导入 ${type}`, () => importFile(type, file))
}

function onDownloadTemplate() {
  const type = importType.value
  runTask(`下载模板 ${type}`, () => downloadTemplate(type))
}

function onExportAssets() {
  const f = assetFilter.value
  runTask('导出资产', () =>
    exportAssets({
      category: f.category || undefined,
      stage: f.stage || undefined,
      warranty_status: f.warranty_status || undefined,
      search: f.search || undefined,
    }),
  )
}

function onExportByType() {
  const type = exportType.value
  runTask(`导出 ${type}`, () => exportByType(type))
}

function onExportStats() {
  runTask('导出统计看板', () => exportStats())
}

function onDownload(id: string | number) {
  const t = tasks.value.find((x) => x.id === id)
  if (t?.op) t.op().catch(() => {})
}
function onRetry(id: string | number) {
  const t = tasks.value.find((x) => x.id === id)
  if (t?.op) runTask(t.name, t.op)
}
function onRemove(id: string | number) {
  tasks.value = tasks.value.filter((x) => x.id !== id)
}
</script>

<template>
  <section>
    <div class="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <nav class="mb-1 text-xs text-slate-400">协同中心 / 导入导出</nav>
        <h1 class="text-xl font-semibold text-slate-800">导入导出</h1>
        <p class="mt-1 text-sm text-slate-500">通过同步接口完成批量导入、模板下载与各类导出；每次操作生成前端任务记录并跟踪状态。</p>
      </div>
    </div>

    <!-- Controls -->
    <div class="grid grid-cols-1 gap-3 lg:grid-cols-3">
      <!-- Import -->
      <div class="c2-panel space-y-2 p-4">
        <h2 class="text-sm font-semibold text-slate-700">批量导入</h2>
        <select v-model="importType" class="c2-input w-full">
          <option v-for="t in MODULE_TYPES" :key="t" :value="t">{{ t }}</option>
        </select>
        <input ref="fileInput" type="file" accept=".xlsx,.xls" class="c2-input w-full text-xs" />
        <button class="c2-btn c2-btn-primary w-full" type="button" @click="onImport">
          <Upload :size="14" /> 导入
        </button>
      </div>

      <!-- Template -->
      <div class="c2-panel space-y-2 p-4">
        <h2 class="text-sm font-semibold text-slate-700">模板下载</h2>
        <select v-model="importType" class="c2-input w-full">
          <option v-for="t in MODULE_TYPES" :key="t" :value="t">{{ t }}</option>
        </select>
        <button class="c2-btn c2-btn-ghost w-full" type="button" @click="onDownloadTemplate">
          <FileDown :size="14" /> 下载模板
        </button>
      </div>

      <!-- Export by module -->
      <div class="c2-panel space-y-2 p-4">
        <h2 class="text-sm font-semibold text-slate-700">模块导出</h2>
        <select v-model="exportType" class="c2-input w-full">
          <option v-for="t in MODULE_TYPES.filter((x) => x !== 'assets')" :key="t" :value="t">{{ t }}</option>
        </select>
        <button class="c2-btn c2-btn-ghost w-full" type="button" @click="onExportByType">导出模块</button>
        <button class="c2-btn c2-btn-ghost w-full" type="button" @click="onExportStats">导出统计看板</button>
      </div>
    </div>

    <!-- Asset export by filter -->
    <div class="mt-3 c2-panel space-y-2 p-4">
      <h2 class="text-sm font-semibold text-slate-700">资产导出（按条件）</h2>
      <div class="flex flex-wrap items-center gap-2">
        <select v-model="assetFilter.category" class="c2-input w-auto text-sm">
          <option value="">全部分类</option>
          <option v-for="c in CATEGORIES" :key="c" :value="c">{{ c }}</option>
        </select>
        <select v-model="assetFilter.stage" class="c2-input w-auto text-sm">
          <option value="">全部生命周期</option>
          <option v-for="s in STAGES" :key="s" :value="s">{{ s }}</option>
        </select>
        <select v-model="assetFilter.warranty_status" class="c2-input w-auto text-sm">
          <option value="">全部维保</option>
          <option v-for="w in WARRANTY" :key="w" :value="w">{{ w }}</option>
        </select>
        <input v-model="assetFilter.search" class="c2-input w-auto flex-1 text-sm" placeholder="搜索关键字" />
        <button class="c2-btn c2-btn-primary" type="button" @click="onExportAssets">导出资产</button>
      </div>
    </div>

    <!-- Task center -->
    <div class="mt-3">
      <div class="mb-2 flex items-center justify-between">
        <h2 class="text-sm font-semibold text-slate-700">任务中心</h2>
        <button class="c2-btn c2-btn-ghost px-2 py-1 text-xs" type="button" @click="tasks = []">
          <RefreshCw :size="13" /> 清空已完成
        </button>
      </div>
      <TaskCenter :tasks="tasks" @download="onDownload" @retry="onRetry" @remove="onRemove" />
    </div>
  </section>
</template>
