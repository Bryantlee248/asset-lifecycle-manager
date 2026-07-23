import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as authService from '@/services/auth'
import type { User } from '@/services/types'

function loadUser(): User | null {
  try {
    const raw = localStorage.getItem('asset_user')
    return raw ? (JSON.parse(raw) as User) : null
  } catch {
    return null
  }
}
function loadToken(): string {
  try {
    return localStorage.getItem('asset_token') || ''
  } catch {
    return ''
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(loadToken())
  const user = ref<User | null>(loadUser())

  const loggedIn = computed(() => !!token.value && !!user.value?.id)
  const permissions = computed<string[]>(() => user.value?.permissions || [])
  const roles = computed(() => user.value?.roles || [])

  async function login(username: string, password: string) {
    const data = await authService.login(username, password)
    token.value = data.token
    user.value = data.user
    return data
  }

  function logout() {
    authService.logout()
    token.value = ''
    user.value = null
  }

  async function fetchMe() {
    const me = await authService.fetchMe()
    user.value = me
    try {
      localStorage.setItem('asset_user', JSON.stringify(me))
    } catch {
      /* ignore */
    }
    return me
  }

  function hasPerm(perm: string): boolean {
    return authService.hasPerm(user.value, perm)
  }

  // React to 401-driven session clears from the api layer.
  if (typeof window !== 'undefined') {
    window.addEventListener('auth:logout', () => {
      token.value = ''
      user.value = null
    })
  }

  return { token, user, loggedIn, permissions, roles, login, logout, fetchMe, hasPerm }
})
