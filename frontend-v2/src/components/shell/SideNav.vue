<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { PanelLeftClose, PanelLeftOpen } from 'lucide-vue-next'
import { NAV_GROUPS } from '@/app/nav'
import { useUiStore } from '@/stores/ui'

const route = useRoute()
const ui = useUiStore()

const isActive = (path: string) => route.path === path

// mobile off-canvas
const mobileOpen = computed(() => ui.navOpen)
function closeMobile() {
  ui.setNav(false)
}
</script>

<template>
  <!-- Desktop persistent rail -->
  <aside
    class="hidden shrink-0 flex-col border-r border-[var(--border)] bg-[var(--surface)] lg:flex"
    :class="ui.navCollapsed ? 'w-16' : 'w-60'"
  >
    <nav class="scroll-thin flex-1 overflow-y-auto py-3">
      <div v-for="group in NAV_GROUPS" :key="group.title" class="mb-2">
        <p
          v-if="!ui.navCollapsed"
          class="px-4 py-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400"
        >
          {{ group.title }}
        </p>
        <RouterLink
          v-for="item in group.items"
          :key="item.key"
          :to="item.path"
          class="mb-0.5 flex items-center gap-3 px-4 py-2 text-sm transition-colors"
          :class="[
            ui.navCollapsed ? 'justify-center' : '',
            isActive(item.path)
              ? 'border-r-2 border-[var(--brand)] bg-[var(--canvas)] font-medium text-[var(--brand)]'
              : 'text-slate-600 hover:bg-[var(--canvas)]',
          ]"
          :title="ui.navCollapsed ? item.label : undefined"
        >
          <component :is="item.icon" :size="18" class="shrink-0" />
          <span v-if="!ui.navCollapsed" class="truncate">{{ item.label }}</span>
        </RouterLink>
      </div>
    </nav>
    <button
      class="flex items-center gap-2 border-t border-[var(--border)] px-4 py-3 text-sm text-slate-500 hover:bg-[var(--canvas)]"
      type="button"
      :aria-label="ui.navCollapsed ? '展开导航' : '折叠导航'"
      @click="ui.toggleCollapse()"
    >
      <PanelLeftClose v-if="!ui.navCollapsed" :size="18" />
      <PanelLeftOpen v-else :size="18" />
      <span v-if="!ui.navCollapsed">收起</span>
    </button>
  </aside>

  <!-- Mobile off-canvas drawer -->
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="mobileOpen" class="fixed inset-0 z-50 lg:hidden">
        <div class="absolute inset-0 bg-black/40" @click="closeMobile"></div>
        <aside class="absolute left-0 top-0 flex h-full w-64 flex-col bg-[var(--surface)] shadow-[var(--shadow)]">
          <nav class="scroll-thin flex-1 overflow-y-auto py-3">
            <div v-for="group in NAV_GROUPS" :key="group.title" class="mb-2">
              <p class="px-4 py-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                {{ group.title }}
              </p>
              <RouterLink
                v-for="item in group.items"
                :key="item.key"
                :to="item.path"
                class="mb-0.5 flex items-center gap-3 px-4 py-2 text-sm transition-colors"
                :class="isActive(item.path)
                  ? 'border-r-2 border-[var(--brand)] bg-[var(--canvas)] font-medium text-[var(--brand)]'
                  : 'text-slate-600 hover:bg-[var(--canvas)]'"
                @click="closeMobile"
              >
                <component :is="item.icon" :size="18" class="shrink-0" />
                <span class="truncate">{{ item.label }}</span>
              </RouterLink>
            </div>
          </nav>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>
