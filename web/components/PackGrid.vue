<template>
  <section class="beatmap-container">
    <header class="packs-header">
      <h3 class="packs-header__title">
        <slot name="title">{{ title }}</slot>
      </h3>
      <p class="packs-header__subtitle">
        Completion: {{ stats.clearedBeatmaps }} / {{ stats.totalBeatmaps }} ({{ stats.percent }}%) · Packs completed:
        {{ stats.completedPacks }} / {{ stats.totalPacks }}
      </p>
    </header>
    <div class="beatmaps">
      <div class="squares">
        <div v-for="pack in packs" :key="pack.id" class="square" :style="{ backgroundColor: colorFor(pack) }"
          @mouseenter="onHover($event, pack)" @mousemove="onHover($event, pack)" @mouseleave="onLeave"
          @click="emit('open', pack)"></div>
      </div>
    </div>
  </section>
</template>

<script setup>
const props = defineProps({
  title: {
    type: String,
    default: '',
  },
  packs: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits(['hover', 'leave', 'open']);

const stats = computed(() => {
  const totalPacks = props.packs.length;
  let completedPacks = 0;
  let totalBeatmaps = 0;
  let clearedBeatmaps = 0;

  props.packs.forEach((pack) => {
    totalBeatmaps += pack.total;
    clearedBeatmaps += pack.cleared;
    if (pack.total > 0 && pack.cleared >= pack.total) {
      completedPacks += 1;
    }
  });

  const percent = totalBeatmaps ? ((clearedBeatmaps / totalBeatmaps) * 100).toFixed(2) : '0.00';

  return { totalPacks, completedPacks, totalBeatmaps, clearedBeatmaps, percent };
});

const colorFor = (pack) => {
  if (!pack.total) {
    return '#444';
  }
  if (pack.cleared >= pack.total) {
    return '#4CAF50';
  }
  if (pack.cleared > 0) {
    return '#FFC107';
  }
  return '#F44336';
};

const onHover = (event, pack) => {
  emit('hover', { event, pack });
};

const onLeave = () => {
  emit('leave');
};
</script>
