<template>
  <teleport to="body">
    <div
      v-if="visible"
      class="custom-tooltip"
      :style="{ top: `${position.y}px`, left: `${position.x}px` }"
    >
      <slot />
    </div>
  </teleport>
</template>

<script setup>
const props = defineProps({
  visible: Boolean,
  position: {
    type: Object,
    default: () => ({ x: 0, y: 0 }),
  },
});
</script>
