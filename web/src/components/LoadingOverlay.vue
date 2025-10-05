<template>
  <teleport to="body">
    <div v-if="visible" class="loading-overlay">
      <div class="loading-spinner" />
      <p v-if="message" class="loading-message">{{ message }}</p>
    </div>
  </teleport>
</template>

<script setup>
defineProps({
  visible: Boolean,
  message: {
    type: String,
    default: '',
  },
});
</script>
