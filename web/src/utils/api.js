import axios from 'axios';

export const api = axios.create({
  baseURL: 'http://127.0.0.1:8000/',
  timeout: 15000,
});

export const handleApiError = (error) => {
  if (error.response) {
    return error.response.data?.detail || `Request failed: ${error.response.status}`;
  }
  if (error.request) {
    return 'Unable to connect to the server, please try again later.';
  }
  return error.message || 'An unknown error occurred.';
};
