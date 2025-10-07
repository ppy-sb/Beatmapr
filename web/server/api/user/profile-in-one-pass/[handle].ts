import { api } from "~/utils/api";
export default defineEventHandler(async (event) => {
  if (!event.context.params) {
    throw createError({ statusCode: 400, message: 'Missing id parameter' });
  }

  let id = Number.parseInt(event.context.params.handle)
  if (Number.isNaN(id)) {
    const { handle: keyword } = event.context.params;
    const data: { id: number }[] = await api('/users/search', {
      params: { query: keyword, limit: 1 },
    })
    id = data.at(0)?.id as number;
  }
  if (!id) {
    throw createError({ statusCode: 404, message: 'User not found' });
  }

  const profile = await api('/users/' + id + '/profile');
  if (!profile) {
    throw createError({ statusCode: 404, message: 'Profile not found' });
  }
  return profile;
});