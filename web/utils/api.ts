const BASE = '/api';
export const api = $fetch.create({
  baseURL: BASE,
})

export const buildEventStreamUrl = (path: string) => {
  const normalisedPath = path.startsWith('/') ? path : `/${path}`;

  return `${BASE}${normalisedPath}`;

};

export const handleApiError = (error: any) => {
  if (error.response) {
    return error.response.data?.detail || `Request failed: ${error.response.status}`;
  }
  if (error.request) {
    return 'Unable to connect to the server, please try again later.';
  }
  return error.message || 'An unknown error occurred.';
};
