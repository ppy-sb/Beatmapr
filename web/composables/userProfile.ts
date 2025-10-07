export function useUserProfile(userStore: ReturnType<typeof useUserStore>) {

  const { profile } = storeToRefs(userStore)

  return {
    profile,
    async getProfileByHandle(userId: string) {
      profile.value = await $fetch('/api/user/profile-in-one-pass/' + userId);
      if (!profile.value) throw new Error('Profile not found.');
      userStore.selectedUserId = profile.value.user.id
    }
  }
}