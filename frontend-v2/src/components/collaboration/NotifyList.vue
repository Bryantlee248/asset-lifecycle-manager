<script setup lang="ts">
// NotifyList — approval notifications segmented into 未读 / 与我相关 / 系统通知.
// Unread items carry a clear visual marker (colored dot + bold); read items are
// dimmed. Clicking an item marks it read (via `markRead`) and notifies the host
// via `click`. A "全部已读" action emits `markAllRead`.

import { ref, computed } from 'vue'
import { CheckCheck } from 'lucide-vue-next'

const props = defineProps<{
  items: any[]
  unreadCount?: number
}>()

const emit = defineEmits<{
  (e: 'markRead', id: string | number): void
  (e: 'markAllRead'): void
  (e: 'click', item: any): void
}>()

type Tab = 'unread' | 'related' | 'system'
const tab = ref<Tab>('unread')

const classified = computed(() => {
  const unread: any[] = []
  const related: any[] = []
  const system: any[] = []
  for (const it of props.items) {
    const isSystem = (it.category || it.type) === 'system'
    if (!it.is_read) unread.push(it)
    if (isSystem) system.push(it)
    else related.push(it)
  }
  return { unread, related, system }
})

const current = computed(() => classified.value[tab.value] || [])

function onItemClick(item: any) {
  emit('click', item)
  if (!item.is_read) emit('markRead', item.id)
}
</script>

<template>
  <div class="c2-panel overflow-hidden">
    <div class="flex items-center justify-between border-b border-[var(--border)] px-3 py-2.5">
      <div class="flex items-center gap-1 text-sm">
        <button
          type="button"
          class="rounded px-2 py-1"
          :class="tab === 'unread' ? 'bg-[var(--canvas)] font-medium text-slate-800' : 'text-slate-500'"
          @click="tab = 'unread'"
        >
          未读<span v-if="classified.unread.length" class="ml-1 text-xs text-[var(--risk-critical)]">{{ classified.unread.length }}</span>
        </button>
        <button
          type="button"
          class="rounded px-2 py-1"
          :class="tab === 'related' ? 'bg-[var(--canvas)] font-medium text-slate-800' : 'text-slate-500'"
          @click="tab = 'related'"
        >
          与我相关
        </button>
        <button
          type="button"
          class="rounded px-2 py-1"
          :class="tab === 'system' ? 'bg-[var(--canvas)] font-medium text-slate-800' : 'text-slate-500'"
          @click="tab = 'system'"
        >
          系统通知
        </button>
      </div>
      <button class="c2-btn c2-btn-ghost px-2 py-1 text-xs" type="button" @click="emit('markAllRead')">
        <CheckCheck :size="13" /> 全部已读
      </button>
    </div>

    <div class="scroll-thin max-h-[60vh] overflow-y-auto">
      <div v-if="!current.length" class="px-3 py-10 text-center text-sm text-slate-400">暂无通知</div>
      <button
        v-for="item in current"
        :key="item.id"
        type="button"
        class="flex w-full items-start gap-2 border-b border-[var(--border)] px-3 py-2.5 text-left transition-colors hover:bg-[var(--canvas)]"
        :class="item.is_read ? 'opacity-60' : ''"
        @click="onItemClick(item)"
      >
        <span
          v-if="!item.is_read"
          class="mt-1.5 inline-block h-2 w-2 shrink-0 rounded-full bg-[var(--risk-critical)]"
          aria-label="未读"
        ></span>
        <span v-else class="mt-1.5 inline-block h-2 w-2 shrink-0"></span>
        <span class="min-w-0 flex-1">
          <span class="block truncate text-sm" :class="item.is_read ? 'font-normal text-slate-500' : 'font-semibold text-slate-800'">
            {{ item.title || item.message || '通知' }}
          </span>
          <span v-if="item.content || item.message" class="mt-0.5 block truncate text-xs text-slate-400">{{ item.content || item.message }}</span>
          <span v-if="item.created_at" class="mt-0.5 block text-xs text-slate-300">{{ item.created_at }}</span>
        </span>
      </button>
    </div>
  </div>
</template>
