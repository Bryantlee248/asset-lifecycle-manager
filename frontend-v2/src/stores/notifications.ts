import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface AppNotification {
  id: string
  title: string
  body?: string
  time?: string
  read?: boolean
}

export const useNotificationsStore = defineStore('notifications', () => {
  // Batch-1 placeholder state. Real approval-driven unread counts land in batch 3.
  const notifications = ref<AppNotification[]>([])
  const approvalUnread = ref(0)

  function markAllRead() {
    notifications.value = notifications.value.map((n) => ({ ...n, read: true }))
    approvalUnread.value = 0
  }

  return { notifications, approvalUnread, markAllRead }
})
