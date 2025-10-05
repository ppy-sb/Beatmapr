<template>
  <section class="profile-section">
    <div class="profile-container">
      <img :src="avatarSrc" alt="Player Avatar" class="profile-avatar" @error="onAvatarError" />
      <div class="profile-info">
        <h2>{{ profile?.user?.username || 'Player' }}</h2>
        <p>Ranked Score: {{ formattedRankedScore }}</p>
        <p>Global Rank: {{ formattedGlobalRank }}</p>
        <div class="rank-counts">
          <div v-for="rank in rankOrder" :key="rank" class="rank-count">
            <img :src="iconFor(rank)" :alt="rank" />
            <span>{{ counts[rank] ?? 0 }}</span>
          </div>
        </div>
        <div class="profile-actions">
          <button class="refresh-button" type="button" @click="emit('refresh')" :disabled="refreshing">
            <span v-if="refreshing" class="button-spinner" />
            {{ refreshing ? 'Refreshing…' : 'Refresh Data' }}
          </button>
          <span v-if="profile?.user?.last_refreshed_at" class="last-updated">
            Last updated: {{ formatDate(profile.user.last_refreshed_at) }}
          </span>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue';

const props = defineProps({
  profile: {
    type: Object,
    default: null,
  },
  counts: {
    type: Object,
    default: () => ({})
  },
  refreshing: Boolean,
});

const emit = defineEmits(['refresh']);

const fallbackAvatar = new URL('../assets/images/default.png', import.meta.url).href;
const avatarSrcState = ref(null);

const avatarSrc = computed(() => {
  if (avatarSrcState.value) {
    return avatarSrcState.value;
  }
  return props.profile?.user?.avatar_url || fallbackAvatar;
});

const rankOrder = ['SSH', 'SS', 'SH', 'S', 'A', 'B', 'C', 'D'];

const formattedRankedScore = computed(() => {
  const score = props.profile?.user?.ranked_score;
  return score ? Number(score).toLocaleString() : '0';
});

const formattedGlobalRank = computed(() => {
  const rank = props.profile?.user?.global_rank;
  return rank ? `#${rank.toLocaleString()}` : '#?';
});

const iconFor = (rank) => new URL(`../assets/images/${rank}.svg`, import.meta.url).href;

const onAvatarError = () => {
  avatarSrcState.value = fallbackAvatar;
};

const formatDate = (value) => {
  if (!value) return 'Unknown';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Unknown';
  return date.toLocaleString();
};
</script>
