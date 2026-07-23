<script setup lang="ts">
defineProps<{
  open: boolean
  title?: string
  message?: string
  confirmText?: string
  cancelText?: string
  danger?: boolean
}>()
const emit = defineEmits<{ (e: 'confirm'): void; (e: 'cancel'): void }>()
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="open"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4"
        role="dialog"
        aria-modal="true"
        @click.self="emit('cancel')"
      >
        <div class="c2-panel w-full max-w-sm p-5 shadow-[var(--shadow)]">
          <h3 class="text-base font-semibold text-slate-800">{{ title || '确认操作' }}</h3>
          <p class="mt-2 text-sm text-slate-600">{{ message || '此操作不可撤销，是否继续？' }}</p>
          <div class="mt-5 flex justify-end gap-2">
            <button class="c2-btn c2-btn-ghost" type="button" @click="emit('cancel')">
              {{ cancelText || '取消' }}
            </button>
            <button
              class="c2-btn"
              :class="danger ? 'bg-[var(--risk-critical)] hover:bg-[#c93b46] text-white' : 'c2-btn-primary'"
              type="button"
              @click="emit('confirm')"
            >
              {{ confirmText || '确认' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
