<script setup lang="ts">
defineProps<{
  width?: string
  height?: string
  rounded?: string
}>()
</script>

<template>
  <div
    class="animate-pulse bg-slate-200/70"
    :style="{ width: width || '100%', height: height || '16px', borderRadius: rounded || 'var(--radius)' }"
  ></div>
</template>
