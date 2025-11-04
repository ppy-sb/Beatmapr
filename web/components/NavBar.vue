<template>
  <nav class="navbar">
    <div class="nav-container">
      <div class="nav-links">
        <NuxtLink active-class="nav-button--active" class="nav-button" to="/">
          Beatmapr
        </NuxtLink>
        <NuxtLink active-class="nav-button--active" class="nav-button" to="/leaderboards">
          Leaderboards
        </NuxtLink>
      </div>
      <div class="input-wrapper">
        <input v-model="searchQuery" type="text" name="player" placeholder="Search player..." autocomplete="off"
          @focus="onFocus" />
        <ul v-if="showSuggestions && suggestions.length" class="suggestions-list">
          <li v-for="user in suggestions" :key="user.id" @click="selectSuggestion(user)">
            <img :src="avatarFor(user.id)" @error="onSuggestionImageError" alt="avatar" />
            <span>{{ user.username }}</span>
          </li>
        </ul>
      </div>
      <slot></slot>
    </div>
  </nav>
</template>
<script setup lang="js">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';

import { useUserStore } from '~/stores/user';
import { useRouter } from 'vue-router';

const userStore = useUserStore();
const router = useRouter();
const searchQuery = ref('');
const showSuggestions = ref(false);

const suggestions = computed(() => userStore.searchResults);
const avatarFor = (id) => `https://a.akatsuki.gg/${id}.png`;

const handleOutsideClick = (event) => {
  if (!event.target.closest('.input-wrapper')) {
    showSuggestions.value = false;
  }
};

onMounted(async () => {
  document.addEventListener('click', handleOutsideClick);
});

onUnmounted(() => {
  document.removeEventListener('click', handleOutsideClick);
});

const selectSuggestion = (user) => {
  router.push(`/users/${user.id}`);
};

const DEBOUNCE_MS = 300;
let searchDebounceTimeout = null;

watch(searchQuery, (newQuery) => {
  if (searchDebounceTimeout) clearTimeout(searchDebounceTimeout);

  searchDebounceTimeout = setTimeout(() => {
    userStore.searchUsers(newQuery);
    showSuggestions.value = true;
    searchDebounceTimeout = null;
  }, DEBOUNCE_MS);
});

onUnmounted(() => {
  if (searchDebounceTimeout) {
    clearTimeout(searchDebounceTimeout);
    searchDebounceTimeout = null;
  }
});
</script>