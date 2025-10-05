<template>
  <div v-if="visible" class="modal" @click.self="close">
    <div class="modal-content">
      <span class="close-btn" @click="close">&times;</span>
      <h2>{{ pack?.pack?.name || 'Pack' }}</h2>
      <p class="modal-subtitle">
        {{ pack?.pack?.slug }} · {{ pack?.pack?.beatmap_count || 0 }} beatmaps
      </p>
      <div class="modal-beatmaps">
        <div v-for="beatmap in pack?.beatmaps || []" :key="beatmap.beatmap_id" class="beatmap-tile"
          :style="backgroundStyle(beatmap)">
          <div class="beatmap-overlay">
            <input type="checkbox" class="beatmap-tile-checkbox" :checked="beatmap.cleared" disabled />
            <div class="beatmap-label" :class="{ 'beatmap-label--cleared': beatmap.cleared }">
              <button class="preview-toggle" type="button" @click="togglePreview(beatmap)">
                {{ currentPreviewId === beatmap.beatmap_id && !audio.paused ? '⏸️' : '▶️' }}
              </button>
              <button class="copy-button" type="button" @click="copyBeatmapId(beatmap.beatmap_id)">
                {{ copiedId === beatmap.beatmap_id ? 'Copied' : beatmap.beatmap_id }}
              </button>
              <span>
                {{ beatmap.title }} [{{ beatmap.version }}]
                · {{ formatDuration(beatmap.hit_length) }}
                <template v-if="beatmap.star_rating">
                  · {{ Number(beatmap.star_rating).toFixed(2) }}★
                </template>
                <template v-if="beatmap.grade">
                  · Grade: {{ beatmap.grade }}
                </template>
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue';

const props = defineProps({
  visible: Boolean,
  pack: {
    type: Object,
    default: null,
  },
});

const emit = defineEmits(['close']);

const audioRef = ref(new Audio());
const copiedId = ref(null);
const currentPreviewId = ref(null);

const audio = computed(() => audioRef.value);

watch(
  () => props.visible,
  (visible) => {
    if (!visible) {
      stopPreview();
    }
  }
);

onBeforeUnmount(() => {
  stopPreview();
});

const close = () => {
  stopPreview();
  emit('close');
};

const formatDuration = (seconds) => {
  if (!seconds && seconds !== 0) return 'N/A';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
};

const copyBeatmapId = async (id) => {
  try {
    await navigator.clipboard.writeText(String(id));
    copiedId.value = id;
    setTimeout(() => {
      copiedId.value = null;
    }, 1200);
  } catch (error) {
    console.error('Copy failed', error);
  }
};

const previewUrl = (beatmap) => {
  if (!beatmap.beatmapset_id) {
    return null;
  }
  return `https://b.ppy.sh/preview/${beatmap.beatmapset_id}.mp3`;
};

const togglePreview = async (beatmap) => {
  const audioEl = audio.value;
  if (!audioEl) return;

  const url = previewUrl(beatmap);
  if (!url) return;

  if (currentPreviewId.value === beatmap.beatmap_id && !audioEl.paused) {
    stopPreview();
    return;
  }

  if (currentPreviewId.value !== beatmap.beatmap_id) {
    currentPreviewId.value = beatmap.beatmap_id;
    audioEl.src = url;
  }

  try {
    await audioEl.play();
    audioEl.volume = 0.1;
  } catch (error) {
    console.error('Playback failed', error);
    currentPreviewId.value = null;
  }
};

const stopPreview = () => {
  const audioEl = audio.value;
  if (audioEl && !audioEl.paused) {
    audioEl.pause();
    audioEl.currentTime = 0;
  }
  currentPreviewId.value = null;
};

const backgroundStyle = (beatmap) => {
  if (!beatmap.beatmapset_id) {
    return { backgroundImage: "url('/images/default_cover.jpg')" };
  }
  return {
    backgroundImage: `url('https://assets.ppy.sh/beatmaps/${beatmap.beatmapset_id}/covers/cover.jpg')`,
  };
};
</script>
