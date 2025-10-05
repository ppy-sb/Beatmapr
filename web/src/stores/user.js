import { defineStore } from 'pinia';
import { api, handleApiError } from '@/utils/api';

export const useUserStore = defineStore('user', {
  state: () => ({
    selectedUserId: null,
    profile: null,
    loadingProfile: false,
    profileError: '',
    refreshing: false,
    searchResults: [],
    searchLoading: false,
    searchError: '',
  }),
  getters: {
    rankCounts(state) {
      return state.profile?.user?.rank_counts ?? {
        SSH: 0,
        SS: 0,
        SH: 0,
        S: 0,
        A: 0,
        B: 0,
        C: 0,
        D: 0,
      };
    },
  },
  actions: {
    async searchUsers(keyword) {
      if (!keyword) {
        this.searchResults = [];
        return;
      }
      this.searchLoading = true;
      this.searchError = '';
      try {
        const { data } = await api.get('/users/search', {
          params: { query: keyword, limit: 10 },
        });
        this.searchResults = data;
      } catch (error) {
        this.searchError = handleApiError(error);
      } finally {
        this.searchLoading = false;
      }
    },
    clearSearch() {
      this.searchResults = [];
      this.searchError = '';
    },
    async fetchProfile(userId) {
      if (!userId) {
        this.profileError = 'Please select a player.';
        return;
      }
      this.loadingProfile = true;
      this.profileError = '';
      try {
        const { data } = await api.get(`/users/${userId}/profile`);
        this.profile = data;
        this.selectedUserId = userId;
      } catch (error) {
        this.profileError = handleApiError(error);
        this.profile = null;
      } finally {
        this.loadingProfile = false;
      }
    },
    async refreshUser(userId = this.selectedUserId) {
      if (!userId) {
        return;
      }
      this.refreshing = true;
      try {
        await api.post(`/users/${userId}/refresh`);
        await this.fetchProfile(userId);
      } catch (error) {
        this.profileError = handleApiError(error);
      } finally {
        this.refreshing = false;
      }
    },
    reset() {
      this.selectedUserId = null;
      this.profile = null;
      this.profileError = '';
      this.refreshing = false;
      this.searchResults = [];
    },
  },
});
