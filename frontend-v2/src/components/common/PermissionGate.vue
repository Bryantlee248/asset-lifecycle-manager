<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{
  perm?: string
  anyOf?: string[]
}>()

const auth = useAuthStore()

// Mirrors legacy `v-if="hasPerm('...')"`. Renders the default slot only when the
// current user passes the permission gate.
const allowed = (() => {
  if (props.anyOf && props.anyOf.length) {
    return props.anyOf.some((p) => auth.hasPerm(p))
  }
  if (props.perm) {
    return auth.hasPerm(props.perm)
  }
  return true
})()
</script>

<template>
  <template v-if="allowed"><slot /></template>
</template>
