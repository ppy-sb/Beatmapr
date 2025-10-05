<template>
  <nav class="navbar">
    <div class="nav-container">
      <div class="nav-links">
        <RouterLink
          :class="['nav-button', route.name === 'home' ? 'nav-button--active' : '']"
          to="/"
        >Home</RouterLink>
        <RouterLink
          :class="['nav-button', route.name === 'leaderboards' ? 'nav-button--active' : '']"
          to="/leaderboards"
        >Leaderboards</RouterLink>
      </div>
      <slot />
    </div>
  </nav>
</template>

<script setup>
import { useRoute } from 'vue-router';

const route = useRoute();
</script>
