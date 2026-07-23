<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Search, CornerDownLeft } from 'lucide-vue-next'
import { ALL_NAV_ITEMS } from '@/app/nav'
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()
const router = useRouter()
const query = ref('')
const activeIndex = ref(0)

const results = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return ALL_NAV_ITEMS
  return ALL_NAV_ITEMS.filter((i) => i.label.toLowerCase().includes(q) || i.key.toLowerCase().includes(q))
})

watch(results, () => (activeIndex.value = 0))

function go(path: string) {
  ui.closeCommandPalette()
  query.value = ''
  router.push(path)
}

function onEnter() {
  const r = results.value[activeIndex.value]
  if (r) go(r.path)
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    activeIndex.value = Math.min(activeIndex.value + 1, results.value.length - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    activeIndex.value = Math.max(activeIndex.value - 1, 0)
  } else if (e.key === 'Enter') {
    onEnter()
  }
}

function onGlobalKey(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    ui.commandPaletteOpen ? ui.closeCommandPalette() : ui.openCommandPalette()
  }
}

onMounted(() => document.addEventListener('keydown', onGlobalKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onGlobalKey))
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="ui.commandPaletteOpen"
        class="fixed inset-0 z-[70] flex items-start justify-center bg-black/30 p-4 pt-[12vh]"
        @click.self="ui.closeCommandPalette()"
      >
        <div class="c2-panel w-full max-w-lg overflow-hidden shadow-[var(--shadow)]">
          <div class="flex items-center gap-2 border-b border-[var(--border)] px-3 py-2.5">
            <Search :size="18" class="text-slate-400" />
            <input
              v-model="query"
              class="flex-1 bg-transparent text-sm outline-none placeholder:text-slate-400"
              placeholder="搜索模块 / 命令…"
              aria-label="命令面板搜索"
              autofocus
              @keydown="onKey"
            />
            <kbd class="rounded bg-[var(--canvas)] px-1.5 text-[11px] text-slate-400">ESC</kbd>
          </div>
          <ul class="scroll-thin max-h-80 overflow-y-auto py-1">
            <li
              v-for="(item, idx) in results"
              :key="item.key"
              class="flex cursor-pointer items-center gap-3 px-3 py-2 text-sm"
              :class="idx === activeIndex ? 'bg-[var(--canvas)] text-[var(--brand)]' : 'text-slate-600'"
              @mouseenter="activeIndex = idx"
              @click="go(item.path)"
            >
              <component :is="item.icon" :size="16" class="shrink-0 text-slate-400" />
              <span>{{ item.label }}</span>
              <CornerDownLeft v-if="idx === activeIndex" :size="14" class="ml-auto text-slate-400" />
            </li>
            <li v-if="!results.length" class="px-3 py-4 text-center text-sm text-slate-400">无匹配结果</li>
          </ul>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
