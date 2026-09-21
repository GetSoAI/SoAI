/* SoAI - Page-owned chat activity duration lifecycle [frontend/assets/ts/pages/chat/controllers/chatpage/lifecycle/activityDurationLifecycleRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_ACTIVITY_COMPACT_BREAKPOINT_PX, CHAT_SELECTORS, resolveActivityDurationDisplayMode } from '@features/chat/public.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatRuntimeServices } from '@pages/chat/state/ChatRuntimeServiceManager.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import { disposeActivityDurationRegistry, initializeActivityDurationRegistry } from '@pages/chat/controllers/page/durations/service.ts';
import type { ChatSettingsStateHost } from '@pages/chat/state/ChatSettingsStateManager.ts';
import { measureLayoutViewport } from '@core/layout/elementGeometry.ts';

interface ActivityDurationDisposalHost extends ChatConversationStateHost, PageDomOwnerHost {}

interface ActivityDurationLifecycleHost extends ActivityDurationDisposalHost {
    runtimeServices: Pick<ChatRuntimeServices, 'timers'>;
    settings: Pick<ChatSettingsStateHost['settings'], 'showActivityElapsedTimeEnabled'>;
}

const durationViewportByHost = new WeakMap<ActivityDurationDisposalHost, HTMLElement>();

const disposeActivityDurationLifecycle = (host: ActivityDurationDisposalHost): void => {
    const registeredViewport = durationViewportByHost.get(host);
    const currentViewport = host.pageDom.optional(CHAT_SELECTORS.MESSAGES_AREA);
    if (registeredViewport) {
        disposeActivityDurationRegistry(registeredViewport);
    }
    if (currentViewport instanceof HTMLElement && currentViewport !== registeredViewport) {
        disposeActivityDurationRegistry(currentViewport);
    }
    durationViewportByHost.delete(host);
};

const reconcileActivityDurationLifecycle = (host: ActivityDurationLifecycleHost): void => {
    const conversationId = host.conversationState.currentConversationId;
    if (!conversationId) {
        disposeActivityDurationLifecycle(host);
        return;
    }
    const viewport = host.pageDom.optional(CHAT_SELECTORS.MESSAGES_AREA);
    const messages = host.pageDom.optional(CHAT_SELECTORS.MESSAGES_CONTAINER);
    if (!(viewport instanceof HTMLElement) || !(messages instanceof HTMLElement)) {
        disposeActivityDurationLifecycle(host);
        return;
    }
    const registeredViewport = durationViewportByHost.get(host);
    if (registeredViewport && registeredViewport !== viewport) {
        disposeActivityDurationRegistry(registeredViewport);
    }
    durationViewportByHost.set(host, viewport);
    initializeActivityDurationRegistry({
        viewport,
        root: messages,
        conversationId,
        timers: {
            setTimer: (callback, delayMs) => host.runtimeServices.timers.setTimer(callback, delayMs),
            clearTimer: (timerId) => host.runtimeServices.timers.clearTimer(timerId)
        },
        getDisplayMode: () => resolveActivityDurationDisplayMode(measureLayoutViewport(viewport).width, CHAT_ACTIVITY_COMPACT_BREAKPOINT_PX, host.settings.showActivityElapsedTimeEnabled())
    });
};

export { disposeActivityDurationLifecycle, reconcileActivityDurationLifecycle };
