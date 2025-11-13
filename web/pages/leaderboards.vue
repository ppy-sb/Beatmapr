<template>
  <main class="content-area">
    <section class="beatmap-container">
      <header class="packs-header">
        <h1 class="packs-header__title">Leaderboards</h1>
        <p class="packs-header__subtitle">
          Total {{ total }} players, showing page {{ page }}.
        </p>
      </header>
      <div class="beatmaps">
        <table class="leaderboard-table">
          <thead>
            <tr>
              <th>Rank</th>
              <th>Username</th>
              <th>Country</th>
              <th>Cleared Maps (%)</th>
              <th>Last Updated</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(entry, index) in entries" :key="entry.user.id" :class="rowClass(index)">
              <td>#{{ (page - 1) * pageSize + index + 1 }}</td>
              <td>
                <nuxt-link class="link" :to="`/users/${entry.user.id}`">{{ entry.user.username }}</nuxt-link>
              </td>
              <td>{{ entry.user.country || '??' }}</td>
              <td>
                {{ entry.cleared_beatmaps.toLocaleString() }}
                ({{ entry.completion_percent?.toFixed(2) ?? '0.00' }}%)
              </td>
              <td>{{ formatDate(entry.last_refreshed_at) }}</td>
            </tr>
            <tr v-if="!entries.length">
              <td colspan="5" style="text-align: center; padding: 1rem;">No data available</td>
            </tr>
          </tbody>
        </table>
        <p v-if="errorMessage" class="status-message">{{ errorMessage }}</p>
        <div class="pagination-controls">
          <button @click="prevPage" :disabled="page === 1">Previous</button>
          <span>Page {{ page }}</span>
          <button @click="nextPage" :disabled="page * pageSize >= total">Next</button>
        </div>
      </div>
    </section>
  </main>
</template>

<script setup>
import { api, handleApiError } from '~/utils/api';

const { transaction } = useLoadingOverlay();

const entries = ref([]);
const page = ref(1);
const pageSize = ref(100);
const total = ref(0);
const errorMessage = ref('');

const fetchLeaderboard = async () => await transaction(
  async () => {
    errorMessage.value = '';
    try {
      const data = await api('/leaderboard', {
        params: { page: page.value, page_size: pageSize.value },
      });
      entries.value = data.results;
      total.value = data.total;
    } catch (error) {
      errorMessage.value = handleApiError(error);
    }
  },
  'Fetching leaderboard\u2026'
);

const prevPage = async () => {
  if (page.value === 1) return;
  page.value -= 1;
  await fetchLeaderboard();
};

const nextPage = async () => {
  if (page.value * pageSize.value >= total.value) return;
  page.value += 1;
  await fetchLeaderboard();
};

const formatDate = (value) => {
  if (!value) return 'N/A';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'N/A';
  return date.toLocaleString();
};

const rowClass = (index) => {
  const absoluteIndex = (page.value - 1) * pageSize.value + index;
  if (absoluteIndex === 0) return 'leaderboard-gold';
  if (absoluteIndex === 1) return 'leaderboard-silver';
  if (absoluteIndex === 2) return 'leaderboard-bronze';
  return '';
};

await fetchLeaderboard();
</script>