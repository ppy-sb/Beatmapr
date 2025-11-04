<script lang="ts" setup>
const { isLoading: visible, message } = useLoadingOverlay()
</script>
<template>
  <div class="page-wrapper">
    <NavBar />
    <NuxtPage />
    <SiteFooter style="margin-top: auto;" />
  </div>
  <div class="loading-overlay" :class="{
    visible,
  }">
    <div class="loading-spinner" />
    <p v-if="message" class="loading-message">{{ message }}</p>
  </div>
</template>
