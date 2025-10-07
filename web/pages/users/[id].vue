<template>

    <div>
        <NavBar />
        <div class="page-wrapper">
            <main class="content-area">
                <p v-if="statusMessage" class="status-message">{{ statusMessage }}</p>
                <ProfileBanner :profile="userStore.profile" :counts="userStore.rankCounts"
                    :refreshing="userStore.refreshing" :progress="userStore.refreshEvents"
                    :progress-status="userStore.refreshStatus" :refresh-error="userStore.refreshError"
                    @refresh="userStore.refreshUser" />
                <div class="grid-section" v-if="showPacks">
                    <PackGrid title="Standard Packs" :packs="userStore.profile?.standard || []" @hover="showTooltip"
                        @leave="hideTooltip" @open="openPack" />
                    <PackGrid title="Other Packs" :packs="userStore.profile?.other || []" @hover="showTooltip"
                        @leave="hideTooltip" @open="openPack" />
                </div>
                <p v-else class="status-message">Please select a player to view progress.</p>
            </main>
            <HoverTooltip :visible="tooltip.visible" :position="tooltip.position">
                <template v-if="tooltip.pack">
                    {{ tooltip.pack.slug }}  {{ tooltip.pack.name }}<br />
                    Completion: {{ tooltip.pack.cleared }} / {{ tooltip.pack.total }} ({{
                        formatPercent(tooltip.pack.completion)
                    }}%)
                </template>
            </HoverTooltip>
            <PackModal :visible="modal.visible" :pack="modal.data" @close="closeModal" />
            <SiteFooter />
        </div>
    </div>
</template>

<script setup lang="ts">
import NavBar from '~/components/NavBar.vue';
import { usePacksStore } from '~/stores/packs';
import { useUserStore } from '~/stores/user';
import { handleApiError } from '~/utils/api';

const route = useRoute('users-id');
const packsStore = usePacksStore();
const userStore = useUserStore();
const uP = useUserProfile(userStore);

const statusMessage = ref('');
let refreshSuccessTimer: string | number | NodeJS.Timeout | undefined = undefined;

const tooltip = reactive({
    visible: false,
    pack: null,
    position: { x: 0, y: 0 },
});

const modal = reactive({
    visible: false,
    data: null,
    loading: false,
});

const showPacks = computed(() => !!(userStore.profile?.standard?.length || userStore.profile?.other?.length));

const refreshStatusHints: Record<string, string> = {
    connecting: 'Connecting to refresh stream\u2026',
    listening: 'Waiting for refresh to start\u2026',
    running: 'Refreshing player data\u2026',
    warning: 'Retrying refresh request\u2026',
    closed: 'Progress stream closed.',
};

watch(
    () => userStore.profileError,
    (error) => {
        statusMessage.value = error || '';
    }
);

watch(
    () => packsStore.error,
    (error) => {
        if (error) {
            statusMessage.value = error;
        }
    }
);

watch(
    () => userStore.profile,
    (profile) => {
        if (profile) {
            statusMessage.value = '';
        }
    }
);

watch(
    () => userStore.refreshError,
    (error) => {
        if (error) {
            statusMessage.value = error;
        }
    }
);

watch(
    () => userStore.refreshStatus,
    (status) => {
        if (status === 'success') {
            clearTimeout(refreshSuccessTimer);
            statusMessage.value = 'Refresh complete.';
            refreshSuccessTimer = setTimeout(() => {
                if (statusMessage.value === 'Refresh complete.') {
                    statusMessage.value = '';
                }
            }, 2500);
            return;
        }

        if (status === 'idle' && !userStore.refreshing && !userStore.refreshError) {
            statusMessage.value = '';
            return;
        }

        if (refreshStatusHints[status] && !userStore.refreshError) {
            statusMessage.value = refreshStatusHints[status];
        }
    },
    { flush: 'post' }
);

onUnmounted(() => {
    clearTimeout(refreshSuccessTimer);
    userStore.closeRefreshStream();
});

function showTooltip({ event, pack }: { event: MouseEvent; pack: any; }) {
    tooltip.visible = true;
    tooltip.pack = pack;

    const padding = 12;
    const tooltipWidth = 220;
    const tooltipHeight = 80;

    let x = event.pageX + padding;
    let y = event.pageY + padding;

    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    if (x + tooltipWidth > viewportWidth) {
        x = event.pageX - tooltipWidth - padding;
    }
    if (y + tooltipHeight > viewportHeight) {
        y = event.pageY - tooltipHeight - padding;
    }

    tooltip.position = { x, y };
}

function hideTooltip() {
    tooltip.visible = false;
    tooltip.pack = null;
}

async function openPack(pack: { id: string; }) {
    if (!userStore.selectedUserId) {
        statusMessage.value = 'Please select a player first.';
        return;
    }
    modal.visible = true;
    modal.loading = true;
    try {
        const data = await packsStore.fetchPackDetail(pack.id, userStore.selectedUserId);
        modal.data = data;
    } catch (error: any) {
        statusMessage.value = error.message || handleApiError(error);
        modal.visible = false;
    } finally {
        modal.loading = false;
    }
}

function closeModal() {
    modal.visible = false;
    modal.data = null;
}

function formatPercent(fraction: number) {
    if (!fraction) return '0.00';
    return (fraction * 100).toFixed(2);
}

await callOnce(async () => {

    if (!route.params.id) {
        statusMessage.value = 'Please select a player to view progress.';
        return;
    }

    await Promise.all([
        await packsStore.fetchSummary(),

        // isNaN(Number.parseInt(route.params.id.toString()))
        //     ? await uP.getProfileByHandle(route.params.id.toString())
        //     : await userStore.fetchProfile(route.params.id.toString()),
        await uP.getProfileByHandle(route.params.id.toString())
    ])

}, { mode: 'navigation' });
</script>
