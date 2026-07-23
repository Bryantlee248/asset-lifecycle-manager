<script setup lang="ts">
const props = defineProps<{
  modelValue?: string
  placeholder?: string
  loading?: boolean
}>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: string): void
  (e: 'submit'): void
  (e: 'reset'): void
}>()

function onInput(e: Event) {
  emit('update:modelValue', (e.target as HTMLInputElement).value)
}
function onSubmit() {
  emit('submit')
}
function onReset() {
  emit('update:modelValue', '')
  emit('reset')
}
</script>

<template>
  <div class="c2-panel flex flex-wrap items-center gap-2 px-3 py-2.5">
    <div class="relative flex-1 min-w-[200px]">
      <svg
        class="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400"
        width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"
      >
        <circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" />
      </svg>
      <input
        class="c2-input w-full pl-8"
        :value="modelValue"
        :placeholder="placeholder || '搜索…'"
        :disabled="loading"
        aria-label="搜索"
        @input="onInput"
        @keyup.enter="onSubmit"
      />
    </div>
    <slot name="filters" />
    <button class="c2-btn c2-btn-ghost" type="button" :disabled="loading" @click="onReset">重置</button>
  </div>
</template>
