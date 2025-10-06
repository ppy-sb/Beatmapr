import { defineStore } from 'pinia';
import { api, handleApiError } from '~/utils/api';

export const usePacksStore = defineStore('packs', {
  state: () => ({
    summary: {
      standard: [],
      other: [],
    },
    summaryLoaded: false,
    loading: false,
    error: '',
    detailCache: {} as Record<string, any>,
  }),
  actions: {
    async fetchSummary(force = false) {
      if (this.summaryLoaded && !force) {
        return;
      }
      this.loading = true;
      this.error = '';
      try {
        const data = await api('/packs/summary');
        this.summary.standard = data.standard || [];
        this.summary.other = data.other || [];
        this.summaryLoaded = true;
      } catch (error) {
        this.error = handleApiError(error);
      } finally {
        this.loading = false;
      }
    },
    async fetchPackDetail(packId: string, userId = null, force = false) {
      const cacheKey = `${packId}:${userId ?? 'none'}`;
      if (!force && this.detailCache[cacheKey]) {
        return this.detailCache[cacheKey];
      }
      try {
        const data = await api(`/packs/${packId}`, {
          params: userId ? { user_id: userId } : {},
        });
        this.detailCache[cacheKey] = data;
        return data;
      } catch (error) {
        throw new Error(handleApiError(error));
      }
    },
    reset() {
      this.summaryLoaded = false;
      this.summary = { standard: [], other: [] };
      this.detailCache = {};
    },
  },
});
