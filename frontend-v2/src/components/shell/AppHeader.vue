<script setup lang="ts">
import { Menu, Command, Boxes } from 'lucide-vue-next'
import { useUiStore } from '@/stores/ui'
import NotificationCenter from './NotificationCenter.vue'
import UserMenu from './UserMenu.vue'

const ui = useUiStore()
</script>

<template>
  <header
    class="flex h-14 shrink-0 items-center gap-3 px-3 text-[var(--command-bar-fg)]"
    style="background: var(--command-bar)"
  >
    <!-- mobile nav toggle -->
    <button
      class="rounded p-1.5 hover:bg-white/10 lg:hidden"
      type="button"
      aria-label="打开导航"
      @click="ui.toggleNav()"
    >
      <Menu :size="20" />
    </button>

    <!-- brand -->
    <div class="flex items-center gap-2 font-semibold tracking-tight">
      <span class="flex h-7 w-7 items-center justify-center rounded bg-white/10">
        <Boxes :size="18" />
      </span>
      <span class="hidden sm:inline">资产全生命周期 · 指挥台</span>
    </div>

    <!-- command palette entry -->
    <button
      class="ml-2 hidden items-center gap-2 rounded border border-white/15 bg-white/5 px-3 py-1.5 text-sm text-white/70 hover:bg-white/10 md:flex"
      type="button"
      aria-label="打开命令面板"
      @click="ui.openCommandPalette()"
    >
      <Command :size="15" />
      <span>搜索 / 命令</span>
      <kbd class="rounded bg-white/10 px-1.5 text-[11px]">⌘K</kbd>
    </button>

    <div class="ml-auto flex items-center gap-1">
      <NotificationCenter />
      <UserMenu />
    </div>
  </header>
</template>
