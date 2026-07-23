<script setup lang="ts">
// Approval notifications — batch 3 collaboration page.
// Segmented 未读 / 与我相关 / 系统通知 via NotifyList; mark single / all read.
// Gate: approval:view

import { ref, onMounted } from 'vue'
import { RefreshCw } from 'lucide-vue-next'
import NotifyList from '@/components/collaboration/NotifyList.vue'
import { useUiStore } from '@/stores/ui'
import {
  getNotifications,
  markNotificationRead,
  markAllNotificationsRead,
  getNotificationUnreadCount,
} from '@/services/notifications'

const ui = useUiStore()
const items = ref<any[]>([])
const unreadCount = ref(0)
const loading = ref(false)

async function load() {
  loading.value = true
  ui.clearError()
  try {
    const [data, unread] = await Promise.all([getNotifications(1), getNotificationUnreadCount()])
    items.value = data.items || []
    unreadCount.value = unread.unread_count || 0
  } catch (e) {
    ui.setError((e as Error).message)
  } finally {
    loading.value = false
  }
}

async function onMarkRead(id: string | number) {
  try {
    await markNotificationRead(id)
    await load()
  } catch (e) {
    ui.setError((e as Error).message)
  }
}
async function onMarkAll() {
  try {
    await markAllNotificationsRead()
    await load()
  } catch (e) {
    ui.setError((e as Error).message)
  }
}
function onClick(_item: any) {
  /* selection handled inside NotifyList (it also marks read) */
}

onMounted(load)
</script>

<template>
  <section>
    <div class="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <nav class="mb-1 text-xs text-slate-400">协同中心 / 审批通知</nav>
        <h1 class="text-xl font-semibold text-slate-800">审批通知</h1>
        <p class="mt-1 text-sm text-slate-500">审批流转通知：未读、与我相关与系统通知分段呈现，支持标记已读。</p>
      </div>
      <button class="c2-btn c2-btn-ghost" type="button" :disabled="loading" @click="load">
        <RefreshCw :size="15" /> 刷新
      </button>
    </div>

    <NotifyList
      :items="items"
      :unread-count="unreadCount"
      @mark-read="onMarkRead"
      @mark-all-read="onMarkAll"
      @click="onClick"
    />
  </section>
</template>
