<script setup lang="ts">
// Primary action bar for the asset detail workbench. Emits intent; the parent
// (AssetDetailWorkbench / AssetsPage) decides what happens (drawer, stage picker).
const props = defineProps<{ asset?: Record<string, any> }>()
const emit = defineEmits<{ (e: 'edit'): void; (e: 'stage'): void }>()
</script>

<template>
  <div class="flex flex-wrap gap-2">
    <button class="c2-btn c2-btn-primary" type="button" @click="emit('stage')">
      变更阶段
    </button>
    <button class="c2-btn c2-btn-ghost" type="button" @click="emit('edit')">
      编辑资产
    </button>
  </div>
</template>
