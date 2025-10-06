<template>
  <!-- content from src/views/HomeView.vue -->
  <div class="page-wrapper">
    <NavBar>
      <form class="search-form" @submit.prevent="onSubmit">
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
        <button type="submit" :disabled="userStore.loadingProfile">Search</button>
      </form>
    </NavBar>

    <main class="content-area">
      <p v-if="statusMessage" class="status-message">{{ statusMessage }}</p>

      <ProfileBanner :profile="userStore.profile" :counts="userStore.rankCounts" :refreshing="userStore.refreshing"
        :progress="userStore.refreshEvents" :progress-status="userStore.refreshStatus"
        :refresh-error="userStore.refreshError" @refresh="userStore.refreshUser" />

      <div class="grid-section" v-if="showPacks">
        <PackGrid title="Standard Packs" :packs="userStore.profile?.standard || []" @hover="showTooltip"
          @leave="hideTooltip" @open="openPack" />

        <PackGrid title="Other Packs" :packs="userStore.profile?.other || []" @hover="showTooltip" @leave="hideTooltip"
          @open="openPack" />
      </div>
      <p v-else class="status-message">Please select a player to view progress.</p>
    </main>

    <HoverTooltip :visible="tooltip.visible" :position="tooltip.position">
      <template v-if="tooltip.pack">
        {{ tooltip.pack.slug }}  {{ tooltip.pack.name }}<br />
        Completion: {{ tooltip.pack.cleared }} / {{ tooltip.pack.total }} ({{ formatPercent(tooltip.pack.completion)
        }}%)
      </template>
    </HoverTooltip>

    <PackModal :visible="modal.visible" :pack="modal.data" @close="closeModal" />

    <SiteFooter />
  </div>
</template>

<script setup>
import defaultAvatar from '~/assets/images/default.png';

import { usePacksStore } from '~/stores/packs';
import { useUserStore } from '~/stores/user';
import { handleApiError } from '~/utils/api';

definePageMeta({
  alias: '/home'
})

const packsStore = usePacksStore();
const userStore = useUserStore();

const searchQuery = ref('');
const showSuggestions = ref(false);
const statusMessage = ref('');
let searchTimer = null;
let refreshSuccessTimer = null;

const tooltip = reactive({
  visible: false,
  pack: null,
  position: { x: 0, y: 0 },
});

const modal = reactive({
  visible: false,
  data: null,
  loading: false,
});

const suggestions = computed(() => userStore.searchResults);

const showPacks = computed(() => Boolean(userStore.profile?.standard?.length || userStore.profile?.other?.length));

const isLoading = computed(() => userStore.loadingProfile || userStore.refreshing || modal.loading || packsStore.loading);

const avatarFor = (id) => `https://a.akatsuki.gg/${id}.png`;

const onSuggestionImageError = (event) => {
  event.target.src = defaultAvatar
};

const refreshStatusHints = {
  connecting: 'Connecting to refresh stream\u2026',
  listening: 'Waiting for refresh to start\u2026',
  running: 'Refreshing player data\u2026',
  warning: 'Retrying refresh request\u2026',
  closed: 'Progress stream closed.',
};

watch(searchQuery, (value) => {
  clearTimeout(searchTimer);
  if (!value) {
    userStore.clearSearch();
    showSuggestions.value = false;
    return;
  }
  searchTimer = setTimeout(() => {
    userStore.searchUsers(value);
    showSuggestions.value = true;
  }, 250);
});

watch(
  () => userStore.profileError,
  (error) => {
    statusMessage.value = error || '';
  }
);

watch(
  () => packsStore.error,
  (error) => {
    if (error) {
      statusMessage.value = error;
    }
  }
);

watch(
  () => userStore.profile,
  (profile) => {
    if (profile) {
      statusMessage.value = '';
    }
  }
);

watch(
  () => userStore.refreshError,
  (error) => {
    if (error) {
      statusMessage.value = error;
    }
  }
);

watch(
  () => userStore.refreshStatus,
  (status) => {
    if (status === 'success') {
      clearTimeout(refreshSuccessTimer);
      statusMessage.value = 'Refresh complete.';
      refreshSuccessTimer = setTimeout(() => {
        if (statusMessage.value === 'Refresh complete.') {
          statusMessage.value = '';
        }
      }, 2500);
      return;
    }

    if (status === 'idle' && !userStore.refreshing && !userStore.refreshError) {
      statusMessage.value = '';
      return;
    }

    if (refreshStatusHints[status] && !userStore.refreshError) {
      statusMessage.value = refreshStatusHints[status];
    }
  }
);

onMounted(async () => {
  if (!packsStore.summaryLoaded) {
    await packsStore.fetchSummary();
  }
  document.addEventListener('click', handleOutsideClick);
});

onUnmounted(() => {
  document.removeEventListener('click', handleOutsideClick);
  clearTimeout(searchTimer);
  clearTimeout(refreshSuccessTimer);
  userStore.closeRefreshStream();
});

const handleOutsideClick = (event) => {
  if (!event.target.closest('.input-wrapper')) {
    showSuggestions.value = false;
  }
};

const selectSuggestion = async (user) => {
  searchQuery.value = user.username;
  await userStore.fetchProfile(user.id);
  statusMessage.value = userStore.profileError;
  showSuggestions.value = false;
};

const onSubmit = async () => {
  const trimmed = searchQuery.value.trim();
  if (!trimmed) {
    statusMessage.value = 'Please enter a player name or ID.';
    return;
  }

  const suggestion = suggestions.value.find((item) =>
    item.username.toLowerCase() === trimmed.toLowerCase()
  );
  const userId = trimmed.match(/^\\d+$/) ? Number(trimmed) : suggestion?.id;

  if (!userId) {
    statusMessage.value = 'Player not found, please select from suggestions.';
    return;
  }

  await userStore.fetchProfile(userId);
  statusMessage.value = userStore.profileError;
  showSuggestions.value = false;
};

const onFocus = () => {
  if (suggestions.value.length) {
    showSuggestions.value = true;
  }
};

const showTooltip = ({ event, pack }) => {
  tooltip.visible = true;
  tooltip.pack = pack;

  const padding = 12;
  const tooltipWidth = 220;
  const tooltipHeight = 80;

  let x = event.pageX + padding;
  let y = event.pageY + padding;

  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;

  if (x + tooltipWidth > viewportWidth) {
    x = event.pageX - tooltipWidth - padding;
  }
  if (y + tooltipHeight > viewportHeight) {
    y = event.pageY - tooltipHeight - padding;
  }

  tooltip.position = { x, y };
};

const hideTooltip = () => {
  tooltip.visible = false;
  tooltip.pack = null;
};

const openPack = async (pack) => {
  if (!userStore.selectedUserId) {
    statusMessage.value = 'Please select a player first.';
    return;
  }
  modal.visible = true;
  modal.loading = true;
  try {
    const data = await packsStore.fetchPackDetail(pack.id, userStore.selectedUserId);
    modal.data = data;
  } catch (error) {
    statusMessage.value = error.message || handleApiError(error);
    modal.visible = false;
  } finally {
    modal.loading = false;
  }
};

const closeModal = () => {
  modal.visible = false;
  modal.data = null;
};

const formatPercent = (fraction) => {
  if (!fraction) return '0.00';
  return (fraction * 100).toFixed(2);
};
</script>
