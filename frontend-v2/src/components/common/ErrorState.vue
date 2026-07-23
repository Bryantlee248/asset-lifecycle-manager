<script setup lang="ts">
defineProps<{
  message?: string
}>()
const emit = defineEmits<{ (e: 'retry'): void }>()
</script>

<template>
  <div class="flex flex-col items-center justify-center gap-3 px-6 py-10 text-center">
    <div class="flex h-10 w-10 items-center justify-center rounded-full bg-[#fde8e8] text-[var(--risk-critical)]">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <path d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
      </svg>
    </div>
    <p class="text-sm font-medium text-slate-600">{{ message || '加载失败，请稍后重试' }}</p>
    <button class="c2-btn c2-btn-ghost" type="button" @click="emit('retry')">重试</button>
  </div>
</template>
