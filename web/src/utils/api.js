import axios from 'axios';

export const api = axios.create({
  baseURL: 'http://127.0.0.1:8000/',
});

const normaliseBaseUrl = () => {
  const configured = api.defaults.baseURL || '';
  return configured.replace(/\/?$/, '');
};

const resolveBrowserOrigin = () => {
  if (typeof window === 'undefined') {
    return '';
  }
  return `${window.location.protocol}//${window.location.host}`;
};

export const buildEventStreamUrl = (path) => {
  const normalisedPath = path.startsWith('/') ? path : `/${path}`;
  const base = normaliseBaseUrl();

  if (base.startsWith('http')) {
    return `${base}${normalisedPath}`;
  }

  const origin = resolveBrowserOrigin();
  if (!origin) {
    return normalisedPath;
  }

  const trimmedOrigin = origin.replace(/\/?$/, '');
  return `${trimmedOrigin}${normalisedPath}`;
};

export const handleApiError = (error) => {
  if (error.response) {
    return error.response.data?.detail || `Request failed: ${error.response.status}`;
  }
  if (error.request) {
    return 'Unable to connect to the server, please try again later.';
  }
  return error.message || 'An unknown error occurred.';
};
