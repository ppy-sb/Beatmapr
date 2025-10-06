import { defineStore } from 'pinia';
import { api, buildEventStreamUrl, handleApiError } from '~/utils/api';

const MAX_PROGRESS_EVENTS = 40;

let refreshStream = null;

const createDeferred = () => {
  const deferred = {
    settled: false,
  };
  deferred.promise = new Promise((resolve, reject) => {
    deferred.resolve = (value) => {
      if (deferred.settled) return;
      deferred.settled = true;
      resolve(value);
    };
    deferred.reject = (reason) => {
      if (deferred.settled) return;
      deferred.settled = true;
      reject(reason);
    };
  });
  return deferred;
};

const disposeRefreshStream = () => {
  if (refreshStream) {
    try {
      refreshStream.close();
    } catch (error) {
      console.warn('Failed to close refresh event stream', error);
    }
    refreshStream = null;
  }
};

export const useUserStore = defineStore('user', {
  state: () => ({
    selectedUserId: null,
    profile: null,
    loadingProfile: false,
    profileError: '',
    refreshing: false,
    refreshStatus: 'idle',
    refreshError: '',
    refreshEvents: [],
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
    latestRefreshEvent(state) {
      return state.refreshEvents.length ? state.refreshEvents[state.refreshEvents.length - 1] : null;
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
        const data = await api('/users/search', {
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
    async fetchProfile(userId, options = {}) {
      const { skipStatusCheck = false } = options;
      if (!userId) {
        this.profileError = 'Please select a player.';
        return;
      }
      this.loadingProfile = true;
      this.profileError = '';
      try {
        const data = await api(`/users/${userId}/profile`);
        this.profile = data;
        this.selectedUserId = userId;
      } catch (error) {
        this.profileError = handleApiError(error);
        this.profile = null;
      } finally {
        this.loadingProfile = false;
      }

      if (!skipStatusCheck && !this.profileError) {
        await this.checkRefreshStatus(userId);
      }
    },
    _handleRefreshEvent(payload) {
      if (!payload || typeof payload !== 'object') {
        return 'ignore';
      }

      const lastEvent = this.refreshEvents[this.refreshEvents.length - 1];
      const lastSequence = lastEvent
        ? String(lastEvent.sequence ?? `${lastEvent.stage}:${lastEvent.timestamp}`)
        : null;
      const incomingSequence = String(payload.sequence ?? `${payload.stage}:${payload.timestamp}`);

      if (!lastEvent || lastSequence !== incomingSequence) {
        this.refreshEvents.push(payload);
        if (this.refreshEvents.length > MAX_PROGRESS_EVENTS) {
          this.refreshEvents.shift();
        }
      }

      if (payload.stage === 'refresh:start') {
        this.refreshStatus = 'running';
      } else if (payload.stage?.endsWith(':retry')) {
        this.refreshStatus = 'warning';
      } else if (this.refreshStatus === 'warning' && payload.status === 'info') {
        this.refreshStatus = 'running';
      }

      if (payload.stage === 'refresh:complete') {
        this.refreshStatus = 'success';
        return 'complete';
      }

      if (payload.stage === 'refresh:error' || payload.status === 'error') {
        this.refreshStatus = 'error';
        this.refreshError = payload.message || 'Refresh failed.';
        return 'error';
      }

      return 'ongoing';
    },
    _openRefreshStream(userId) {
      const ready = createDeferred();
      const completion = createDeferred();

      try {
        const url = buildEventStreamUrl(`/users/${userId}/refresh/stream`);
        refreshStream = new EventSource(url);
      } catch (error) {
        ready.reject(error);
        completion.reject(error);
        return { ready: ready.promise, completion: completion.promise };
      }

      const settleCompletion = (result) => {
        if (!completion.settled) {
          completion.resolve(result);
        }
      };

      refreshStream.onopen = () => {
        this.refreshStatus = 'listening';
        ready.resolve();
      };

      refreshStream.onmessage = (event) => {
        if (!event.data) {
          return;
        }
        let payload;
        try {
          payload = JSON.parse(event.data);
        } catch (error) {
          console.warn('Invalid refresh event payload', error, event.data);
          return;
        }
        const outcome = this._handleRefreshEvent(payload);
        if (outcome === 'complete') {
          settleCompletion({ success: true, event: payload });
          disposeRefreshStream();
        } else if (outcome === 'error') {
          settleCompletion({ success: false, event: payload });
          disposeRefreshStream();
        }
      };

      refreshStream.onerror = (event) => {
        console.error('Refresh event stream error', event);
        if (!ready.settled) {
          ready.reject(event);
        }
        if (!completion.settled) {
          if (!this.refreshError) {
            this.refreshError = 'Refresh progress connection failed.';
          }
          if (this.refreshStatus !== 'success' && this.refreshStatus !== 'error') {
            this.refreshStatus = 'error';
          }
          completion.reject(event);
        }
        const stream = event?.target ?? refreshStream;
        if (stream && stream.readyState === EventSource.CLOSED) {
          if (this.refreshStatus !== 'success' && this.refreshStatus !== 'error') {
            this.refreshStatus = 'closed';
          }
          disposeRefreshStream();
        }
      };

      return { ready: ready.promise, completion: completion.promise };
    },
    async refreshUser(userId = this.selectedUserId, options = {}) {
      const { trigger = true, resetEvents = trigger } = options;
      if (!userId) {
        return;
      }

      if (this.refreshing) {
        if (trigger || refreshStream) {
          return;
        }
      }

      if (resetEvents) {
        this.refreshEvents = [];
      }
      this.refreshError = '';
      this.refreshStatus = 'connecting';
      disposeRefreshStream();
      this.refreshing = true;

      const { ready, completion } = this._openRefreshStream(userId);

      try {
        await ready;
      } catch (error) {
        this.refreshError = 'Unable to connect to refresh progress stream.';
        this.refreshStatus = 'error';
        this.refreshing = false;
        completion.catch(() => { });
        disposeRefreshStream();
        return;
      }

      let result;
      try {
        if (trigger) {
          await api(`/users/${userId}/refresh`, { method: 'POST' });
        }

        result = await completion.catch((error) => {
          if (!this.refreshError) {
            this.refreshError = 'Refresh progress stream was interrupted.';
          }
          this.refreshStatus = 'error';
          throw error;
        });

        if (result?.success) {
          await this.fetchProfile(userId, { skipStatusCheck: true });
        } else if (result?.event?.message) {
          this.profileError = result.event.message;
        }
      } catch (error) {
        if (trigger) {
          this.profileError = handleApiError(error);
          this.refreshStatus = 'error';
          this.refreshError = this.profileError;
        }
        completion.catch(() => { });
      } finally {
        disposeRefreshStream();
        this.refreshing = false;
        if (this.refreshStatus === 'warning') {
          this.refreshStatus = 'running';
        }
      }

      return result;
    },
    async checkRefreshStatus(userId = this.selectedUserId) {
      if (!userId) {
        return;
      }

      try {
        const data = await api(`/users/${userId}/refresh/status`);
        const { active = false, last_event: lastEvent = null } = data || {};

        this.refreshEvents = [];
        this.refreshError = '';

        if (lastEvent) {
          this._handleRefreshEvent(lastEvent);
        } else if (!active) {
          this.refreshStatus = 'idle';
        }

        if (active) {
          this.refreshing = false;
          const resumePromise = this.refreshUser(userId, { trigger: false, resetEvents: false });
          resumePromise.catch((error) => {
            console.error('Failed to resume refresh stream', error);
          });
        } else {
          this.refreshing = false;
        }
      } catch (error) {
        console.warn('Failed to check refresh status', error);
      }
    },
    reset() {
      this.selectedUserId = null;
      this.profile = null;
      this.profileError = '';
      this.refreshing = false;
      this.refreshStatus = 'idle';
      this.refreshError = '';
      this.refreshEvents = [];
      this.searchResults = [];
      disposeRefreshStream();
    },
    closeRefreshStream() {
      disposeRefreshStream();
    },
  },
});
