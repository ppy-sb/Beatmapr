<template>
  <div ref="root" :class="{
    visible
  }" class="custom-tooltip" :style="{ top: `${position.y}px`, left: `${position.x}px` }">
    <slot />
  </div>
</template>

<script setup>
const props = defineProps({
  visible: Boolean,
  position: {
    type: Object,
    default: () => ({ x: 0, y: 0 }),
  },
});

const el = useTemplateRef('root')

defineExpose({
  el,
})

</script>

<style scoped>
.custom-tooltip {
  white-space: nowrap;
  opacity: 0;
  transition-duration: 0.2s;
  transition-property: opacity;
  transition-timing-function: ease-in;
}

.custom-tooltip.visible {
  opacity: 1;
  transition-duration: 0.1s;
}
</style>
