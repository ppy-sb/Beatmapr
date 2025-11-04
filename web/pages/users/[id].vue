<template>
    <div class="w">
        <div class="sm-container">
            <p :class="{
                visible: statusMessage !== 'Refresh complete.' && !!statusMessage
            }" class="status-message">
                {{ statusMessage || '　' }}
            </p>
        </div>
        <main class="content-area">
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
        <hover-tooltip :visible="tooltip.visible" :position="tooltip.position" ref="tt">
            <template v-if="tooltip.pack">
                {{ tooltip.pack.slug }}  {{ tooltip.pack.name }}<br />
                Completion: {{ tooltip.pack.cleared }} / {{ tooltip.pack.total }} ({{
                    formatPercent(tooltip.pack.completion)
                }}%)
            </template>
        </hover-tooltip>
        <PackModal :visible="modal.visible" :pack="modal.data" @close="closeModal" />
    </div>
</template>

<script setup lang="ts">
import { usePacksStore } from '~/stores/packs';
import { useUserStore } from '~/stores/user';
import { handleApiError } from '~/utils/api';
import { type HoverTooltip } from '#components';

const route = useRoute('users-id');
const packsStore = usePacksStore();
const userStore = useUserStore();
const uP = useUserProfile(userStore);
const { transaction: withLoadingOverlay } = useLoadingOverlay();

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

const tt = useTemplateRef<InstanceType<typeof HoverTooltip>>('tt')

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

async function showTooltip({ event, pack }: { event: PointerEvent; pack: any; }) {
    await nextTick();
    tooltip.visible = true;
    tooltip.pack = pack;

    const padding = 12;
    const tooltipWidth = tt.value?.el?.offsetWidth || 0;
    const tooltipHeight = tt.value?.el?.offsetHeight || 0;

    let x = event.pageX + padding;
    let y = event.pageY + padding;

    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    if (x + tooltipWidth > viewportWidth) {
        x = event.pageX - tooltipWidth;
    }
    if (y + tooltipHeight > viewportHeight) {
        y = event.pageY - tooltipHeight;
    }

    tooltip.position = { x, y };
}

function hideTooltip() {
    tooltip.visible = false;
    // tooltip.pack = null;
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

async function init() {
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
}

await callOnce(async () => {

    if (import.meta.server) {
        await init();
        return;
    } else {

        await withLoadingOverlay(init, 'Loading user profile and packs...')
    }

}, { mode: 'navigation' });
</script>

<style scoped>
.w {
    max-width: 1100px;
    width: 100%;
    align-self: center;
}


.sm-container {
    overflow: hidden;
}

.status-message {
    /* from visible to invisible */
    transition-property: opacity, margin, padding;
    transition-duration: 0.2s;
    transition-timing-function: ease-out;

    opacity: 0;
    content-visibility: hidden;
    margin: 0;
    margin-top: -100%;
    padding: 0;
}

.status-message:not(.visible) {
    transition-delay: 2s;
}

.status-message.visible {
    /* from invisible to visible */
    transition-timing-function: ease;
    transition-delay: 0s;

    opacity: 1;
    content-visibility: visible;
    margin-top: 0;
    padding-top: 1em;
}
</style>
