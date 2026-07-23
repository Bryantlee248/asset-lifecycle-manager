<script setup lang="ts">
import { ref, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ChevronDown, LogOut, KeyRound } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { api } from '@/services/api'

const auth = useAuthStore()
const ui = useUiStore()
const router = useRouter()

const open = ref(false)
const menuRef = ref<HTMLElement | null>(null)

const pwdOpen = ref(false)
const oldPwd = ref('')
const newPwd = ref('')
const confirmPwd = ref('')
const saving = ref(false)

function toggle() {
  open.value = !open.value
}
function onClickOutside(e: MouseEvent) {
  if (menuRef.value && !menuRef.value.contains(e.target as Node)) open.value = false
}
document.addEventListener('click', onClickOutside)
onBeforeUnmount(() => document.removeEventListener('click', onClickOutside))

function doLogout() {
  auth.logout()
  open.value = false
  router.push('/login')
}

async function savePwd() {
  if (newPwd.value.length < 6) {
    ui.setError('新密码至少 6 位')
    return
  }
  if (newPwd.value !== confirmPwd.value) {
    ui.setError('两次密码不一致')
    return
  }
  saving.value = true
  try {
    await api('/api/auth/change-password', {
      method: 'PUT',
      body: JSON.stringify({ old_password: oldPwd.value, new_password: newPwd.value }),
    })
    pwdOpen.value = false
    oldPwd.value = ''
    newPwd.value = ''
    confirmPwd.value = ''
    ui.clearError()
  } catch (e) {
    ui.setError((e as Error).message)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div ref="menuRef" class="relative">
    <button
      class="flex items-center gap-1.5 rounded px-2 py-1.5 text-sm hover:bg-white/10"
      type="button"
      aria-label="用户菜单"
      @click.stop="toggle"
    >
      <span class="flex h-7 w-7 items-center justify-center rounded-full bg-white/15 text-xs font-semibold">
        {{ (auth.user?.name || auth.user?.username || 'U').toString().slice(0, 1).toUpperCase() }}
      </span>
      <span class="hidden max-w-[120px] truncate sm:inline">{{ auth.user?.name || auth.user?.username }}</span>
      <ChevronDown :size="15" />
    </button>

    <Transition name="fade">
      <div
        v-if="open"
        class="c2-panel absolute right-0 top-full z-50 mt-1 w-44 overflow-hidden py-1 shadow-[var(--shadow)]"
      >
        <button
          class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-slate-600 hover:bg-[var(--canvas)]"
          type="button"
          @click="open = false; pwdOpen = true"
        >
          <KeyRound :size="15" /> 修改密码
        </button>
        <button
          class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--risk-critical)] hover:bg-[var(--canvas)]"
          type="button"
          @click="doLogout"
        >
          <LogOut :size="15" /> 退出登录
        </button>
      </div>
    </Transition>

    <!-- change password modal -->
    <Teleport to="body">
      <Transition name="fade">
        <div
          v-if="pwdOpen"
          class="fixed inset-0 z-[60] flex items-center justify-center bg-black/30 p-4"
          role="dialog"
          aria-modal="true"
          @click.self="pwdOpen = false"
        >
          <div class="c2-panel w-full max-w-sm p-5 shadow-[var(--shadow)]">
            <h3 class="text-base font-semibold text-slate-800">修改密码</h3>
            <div class="mt-3 space-y-3">
              <label class="block text-sm">
                <span class="text-slate-500">原密码</span>
                <input v-model="oldPwd" type="password" class="c2-input mt-1 w-full" />
              </label>
              <label class="block text-sm">
                <span class="text-slate-500">新密码</span>
                <input v-model="newPwd" type="password" class="c2-input mt-1 w-full" />
              </label>
              <label class="block text-sm">
                <span class="text-slate-500">确认新密码</span>
                <input v-model="confirmPwd" type="password" class="c2-input mt-1 w-full" />
              </label>
            </div>
            <div class="mt-5 flex justify-end gap-2">
              <button class="c2-btn c2-btn-ghost" type="button" @click="pwdOpen = false">取消</button>
              <button class="c2-btn c2-btn-primary" type="button" :disabled="saving" @click="savePwd">
                {{ saving ? '提交中…' : '提交' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>
