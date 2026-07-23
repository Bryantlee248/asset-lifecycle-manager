<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Boxes, Lock, User } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'

const auth = useAuthStore()
const ui = useUiStore()
const router = useRouter()

const username = ref('')
const password = ref('')
const loading = ref(false)

async function onSubmit() {
  if (!username.value || !password.value) {
    ui.setError('请输入用户名和密码')
    return
  }
  loading.value = true
  ui.clearError()
  try {
    await auth.login(username.value, password.value)
    router.push('/command-center/dashboard')
  } catch (e) {
    ui.setError((e as Error).message)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-[var(--canvas)] px-4">
    <div class="w-full max-w-sm">
      <div class="mb-6 flex flex-col items-center gap-2 text-center">
        <span class="flex h-12 w-12 items-center justify-center rounded-lg bg-[var(--brand)] text-white">
          <Boxes :size="26" />
        </span>
        <h1 class="text-xl font-semibold text-slate-800">IT资产全生命周期管理系统</h1>
        <p class="text-sm text-slate-500">指挥台 · 统一登录</p>
      </div>

      <form class="c2-panel space-y-4 p-6 shadow-[var(--shadow)]" @submit.prevent="onSubmit">
        <label class="block">
          <span class="mb-1 block text-sm text-slate-600">用户名</span>
          <div class="relative">
            <User class="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" :size="16" />
            <input v-model="username" class="c2-input w-full pl-8" autocomplete="username" aria-label="用户名" />
          </div>
        </label>
        <label class="block">
          <span class="mb-1 block text-sm text-slate-600">密码</span>
          <div class="relative">
            <Lock class="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" :size="16" />
            <input v-model="password" type="password" class="c2-input w-full pl-8" autocomplete="current-password" aria-label="密码" />
          </div>
        </label>

        <p v-if="ui.errorMsg" class="rounded bg-[#fde8e8] px-3 py-2 text-sm text-[var(--risk-critical)]">
          {{ ui.errorMsg }}
        </p>

        <button class="c2-btn c2-btn-primary w-full" type="submit" :disabled="loading">
          {{ loading ? '登录中…' : '登 录' }}
        </button>
      </form>
      <p class="mt-4 text-center text-xs text-slate-400">C2 现代化前端 · 批次一</p>
    </div>
  </div>
</template>
