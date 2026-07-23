<script setup lang="ts">
import { ref, onBeforeUnmount } from 'vue'
import { Bell } from 'lucide-vue-next'
import { useNotificationsStore } from '@/stores/notifications'

const notifications = useNotificationsStore()
const open = ref(false)
const refEl = ref<HTMLElement | null>(null)

function toggle() {
  open.value = !open.value
}
function onClickOutside(e: MouseEvent) {
  if (refEl.value && !refEl.value.contains(e.target as Node)) open.value = false
}
document.addEventListener('click', onClickOutside)
onBeforeUnmount(() => document.removeEventListener('click', onClickOutside))
</script>

<template>
  <div ref="refEl" class="relative">
    <button
      class="relative rounded p-1.5 hover:bg-white/10"
      type="button"
      aria-label="通知中心"
      @click.stop="toggle"
    >
      <Bell :size="18" />
      <span
        v-if="notifications.approvalUnread > 0"
        class="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-[var(--risk-critical)] px-1 text-[10px] font-semibold text-white"
      >
        {{ notifications.approvalUnread > 99 ? '99+' : notifications.approvalUnread }}
      </span>
    </button>

    <Transition name="fade">
      <div
        v-if="open"
        class="c2-panel absolute right-0 top-full z-50 mt-1 w-72 overflow-hidden py-1 shadow-[var(--shadow)]"
      >
        <div class="border-b border-[var(--border)] px-3 py-2 text-sm font-medium text-slate-700">通知中心</div>
        <div class="px-3 py-8 text-center text-sm text-slate-400">
          暂无新通知
        </div>
      </div>
    </Transition>
  </div>
</template>
