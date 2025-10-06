export const getApiBaseUrl = () => {
  return import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
};
export default defineEventHandler(async (event) => {

  const targetUrl = getApiBaseUrl() + event.path.replace(/^\/api/, '');

  console.log('Proxying request to:', targetUrl);

  return proxyRequest(event, targetUrl);
});