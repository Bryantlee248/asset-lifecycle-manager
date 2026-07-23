import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUiStore = defineStore('ui', () => {
  const navOpen = ref(false) // mobile off-canvas drawer
  const navCollapsed = ref(false) // desktop collapse to icon rail
  const globalLoading = ref(false)
  const errorMsg = ref('')
  const commandPaletteOpen = ref(false)

  function toggleNav() {
    navOpen.value = !navOpen.value
  }
  function setNav(open: boolean) {
    navOpen.value = open
  }
  function toggleCollapse() {
    navCollapsed.value = !navCollapsed.value
  }
  function setLoading(v: boolean) {
    globalLoading.value = v
  }
  function setError(msg: string) {
    errorMsg.value = msg
  }
  function clearError() {
    errorMsg.value = ''
  }
  function openCommandPalette() {
    commandPaletteOpen.value = true
  }
  function closeCommandPalette() {
    commandPaletteOpen.value = false
  }

  return {
    navOpen,
    navCollapsed,
    globalLoading,
    errorMsg,
    commandPaletteOpen,
    toggleNav,
    setNav,
    toggleCollapse,
    setLoading,
    setError,
    clearError,
    openCommandPalette,
    closeCommandPalette,
  }
})
