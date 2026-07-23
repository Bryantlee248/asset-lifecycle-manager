<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { AlertTriangle, X } from 'lucide-vue-next'
import AppHeader from '@/components/shell/AppHeader.vue'
import SideNav from '@/components/shell/SideNav.vue'
import CommandPalette from '@/components/shell/CommandPalette.vue'
import StatusBar from '@/components/common/StatusBar.vue'
import { useUiStore } from '@/stores/ui'

const route = useRoute()
const ui = useUiStore()

const isPublic = computed(() => !!(route.meta as any).public)
</script>

<template>
  <div class="flex h-screen flex-col bg-[var(--canvas)]">
    <template v-if="isPublic">
      <RouterView />
    </template>

    <template v-else>
      <AppHeader />
      <div class="flex flex-1 overflow-hidden">
        <SideNav />
        <main class="scroll-thin flex-1 overflow-y-auto">
          <Transition name="fade" mode="out-in">
            <div :key="route.fullPath" class="mx-auto max-w-[1400px] px-4 py-4 sm:px-6">
              <div
                v-if="ui.errorMsg"
                class="mb-4 flex items-center gap-2 rounded border border-[#f3c2c6] bg-[#fde8e8] px-3 py-2 text-sm text-[var(--risk-critical)]"
              >
                <AlertTriangle :size="16" />
                <span class="flex-1">{{ ui.errorMsg }}</span>
                <button class="rounded p-0.5 hover:bg-white/60" type="button" aria-label="关闭错误提示" @click="ui.clearError()">
                  <X :size="15" />
                </button>
              </div>
              <RouterView />
            </div>
          </Transition>
        </main>
      </div>
      <StatusBar />
      <CommandPalette />
    </template>
  </div>
</template>
