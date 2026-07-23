<script setup lang="ts">
defineProps<{
  title?: string
  description?: string
  icon?: boolean
}>()
</script>

<template>
  <div class="flex flex-col items-center justify-center gap-2 px-6 py-10 text-center">
    <div v-if="icon" class="text-3xl text-slate-300">∅</div>
    <p class="text-sm font-medium text-slate-500">{{ title || '暂无数据' }}</p>
    <p v-if="description" class="max-w-sm text-xs text-slate-400">{{ description }}</p>
    <slot />
  </div>
</template>
