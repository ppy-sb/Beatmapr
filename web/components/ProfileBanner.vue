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
          <div v-if="refreshing || renderedProgress.length" class="refresh-status">
            <p v-if="statusText" class="status-text" :class="statusClass">{{ statusText }}</p>
            <ul v-if="renderedProgress.length" class="progress-log">
              <li v-for="event in renderedProgress" :key="event.sequence">
                <span class="time">{{ event.timeText }}</span>
                <span class="stage" :class="event.statusClass">{{ event.stageLabel }}</span>
                <span class="message" :class="event.statusClass">{{ event.message }}</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import fallbackAvatar from '~/assets/images/default.png';
import SSH from '~/assets/images/SSH.svg';
import SS from '~/assets/images/SS.svg';
import SH from '~/assets/images/SH.svg';
import S from '~/assets/images/S.svg';
import A from '~/assets/images/A.svg';
import B from '~/assets/images/B.svg';
import C from '~/assets/images/C.svg';
import D from '~/assets/images/D.svg';

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
  progress: {
    type: Array,
    default: () => [],
  },
  progressStatus: {
    type: String,
    default: 'idle',
  },
  refreshError: {
    type: String,
    default: '',
  },
});

const emit = defineEmits(['refresh']);

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

const url = {
  SSH,
  SS,
  SH,
  S,
  A,
  B,
  C,
  D
}


const iconFor = (rank) => url[rank] || '';

const onAvatarError = () => {
  avatarSrcState.value = fallbackAvatar;
};

const formatDate = (value) => {
  if (!value) return 'Unknown';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Unknown';
  return date.toLocaleString();
};

const formatTime = (value) => {
  if (!value) return '--:--:--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '--:--:--';
  return date.toLocaleTimeString();
};

const stageLabelFor = (stage) => {
  if (!stage) {
    return 'Progress';
  }
  return stage
    .split(':')
    .map((segment) => segment.replace(/_/g, ' '))
    .map((segment) => segment.replace(/\b\w/g, (char) => char.toUpperCase()))
    .join(' · ');
};

const eventStatusClass = (event) => {
  if (!event) return 'status-muted';
  if (event.status === 'error') return 'status-error';
  if (event.status === 'success') return 'status-success';
  if (event.status === 'warning') return 'status-warning';
  return 'status-info';
};

const latestEvents = computed(() => props.progress.slice(-6));

const latestEvent = computed(() => {
  const events = latestEvents.value;
  return events.length ? events[events.length - 1] : null;
});

const renderedProgress = computed(() =>
  latestEvents.value.map((event, index) => ({
    sequence: event.sequence ?? `${event.stage ?? 'stage'}-${event.timestamp ?? index}`,
    timeText: formatTime(event.timestamp),
    stageLabel: stageLabelFor(event.stage),
    message: event.message || stageLabelFor(event.stage),
    statusClass: eventStatusClass(event),
  }))
);

const statusText = computed(() => {
  if (props.refreshError) {
    return props.refreshError;
  }

  const lastEvent = latestEvent.value;
  if (props.progressStatus === 'success') {
    return 'Refresh complete.';
  }
  if (props.progressStatus === 'error') {
    return lastEvent?.message || 'Refresh failed.';
  }
  if (props.progressStatus === 'warning') {
    return lastEvent?.message || 'Retrying…';
  }
  if (props.progressStatus === 'running') {
    return lastEvent?.message || 'Refreshing user data…';
  }
  if (props.progressStatus === 'listening' || props.progressStatus === 'connecting') {
    return 'Preparing refresh…';
  }
  if (props.progressStatus === 'closed') {
    return 'Progress stream closed.';
  }
  if (!lastEvent) {
    return '';
  }
  return lastEvent.message || stageLabelFor(lastEvent.stage);
});

const statusClass = computed(() => {
  if (props.refreshError || props.progressStatus === 'error') {
    return 'status-error';
  }
  if (props.progressStatus === 'success') {
    return 'status-success';
  }
  if (props.progressStatus === 'warning') {
    return 'status-warning';
  }
  if (props.progressStatus === 'running') {
    return 'status-info';
  }
  return 'status-muted';
});
</script>

<style scoped>
.refresh-status {
  flex: 1 1 100%;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  background-color: rgba(17, 17, 17, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 0.75rem 1rem;
}

.status-text {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 600;
}

.progress-log {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.progress-log li {
  display: grid;
  grid-template-columns: 80px 150px 1fr;
  gap: 0.35rem 0.75rem;
  font-size: 0.85rem;
  align-items: center;
}

.progress-log .time {
  font-family: 'Fira Code', 'Roboto Mono', monospace;
  font-size: 0.75rem;
  color: #9e9e9e;
}

.progress-log .stage {
  font-weight: 600;
  text-transform: none;
  color: #d6d6d6;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.progress-log .message {
  white-space: normal;
}

@media (max-width: 768px) {
  .progress-log li {
    grid-template-columns: 70px 1fr;
    grid-template-areas:
      'time message'
      'stage message';
  }

  .progress-log .time {
    grid-area: time;
  }

  .progress-log .stage {
    grid-area: stage;
  }

  .progress-log .message {
    grid-area: message;
  }
}

.status-info {
  color: #64b5f6;
}

.status-success {
  color: #66bb6a;
}

.status-warning {
  color: #ffb74d;
}

.status-error {
  color: #ef5350;
}

.status-muted {
  color: #bdbdbd;
}
</style>
