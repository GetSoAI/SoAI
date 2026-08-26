/* SoAI - Page-owned chat activity duration lifecycle [frontend/assets/ts/pages/chat/controllers/chatpage/lifecycle/activityDurationLifecycleRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_SELECTORS } from '@features/chat/public.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatRuntimeServices } from '@pages/chat/state/ChatRuntimeServiceManager.ts';
import type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import { disposeActivityDurationRegistry, initializeActivityDurationRegistry } from '@pages/chat/controllers/page/durations/service.ts';

interface ActivityDurationLifecycleHost extends ChatConversationStateHost, ChatConversationViewHost, PageDomOwnerHost {
    runtimeServices: Pick<ChatRuntimeServices, 'timers'>;
}

const durationViewportByHost = new WeakMap<ActivityDurationLifecycleHost, HTMLElement>();

const disposeActivityDurationLifecycle = (host: ActivityDurationLifecycleHost): void => {
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
        }
    });
};

export { disposeActivityDurationLifecycle, reconcileActivityDurationLifecycle };
