<script setup lang="ts">
defineProps<{
  open: boolean
  title?: string
  width?: string
}>()
const emit = defineEmits<{ (e: 'close'): void }>()
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="open" class="fixed inset-0 z-40 flex justify-end bg-black/30" @click.self="emit('close')">
        <aside
          class="c2-panel flex h-full w-full max-w-md flex-col rounded-none border-l shadow-[var(--shadow)]"
          :style="{ width: width || '420px' }"
          role="dialog"
          aria-modal="true"
        >
          <header class="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
            <h3 class="text-sm font-semibold text-slate-800">{{ title || '详情' }}</h3>
            <button
              class="rounded p-1 text-slate-400 hover:bg-[var(--canvas)] hover:text-slate-700"
              type="button"
              aria-label="关闭抽屉"
              @click="emit('close')"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <path d="M18 6 6 18M6 6l12 12" />
              </svg>
            </button>
          </header>
          <div class="scroll-thin flex-1 overflow-y-auto px-4 py-3">
            <slot />
          </div>
          <footer v-if="$slots.footer" class="border-t border-[var(--border)] px-4 py-3">
            <slot name="footer" />
          </footer>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>
