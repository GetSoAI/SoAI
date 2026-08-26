/* SoAI - Shared routing streams [frontend/assets/ts/core/routing/pages/basepagestreams/streams.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getStreamRuntime, type StreamRuntimeOwners } from '@core/realtime/streammanager/public.ts';
import { err, request } from '@core/routing/pages/basepagecore/actions.ts';
import type { BasePageStreamsState, SubscriptionManager } from '@core/routing/pages/basepagestreams/internalContracts.ts';
import { StreamHandleTracker } from '@core/routing/pages/pageStreams.ts';
import { subscriptionManager } from '@core/subscriptionmanager/service.ts';

const getOrCreatePageStreamTracker = (state: BasePageStreamsState, pageKey: string): StreamHandleTracker => {
    if (!state.streamTrackers) {
        state.streamTrackers = new Map();
    }
    if (!state.streamTrackers.has(pageKey)) {
        state.streamTrackers.set(pageKey, new StreamHandleTracker(pageKey));
    }
    const tracker = state.streamTrackers.get(pageKey);
    if (!tracker) {
        throw err(`Stream tracker '${pageKey}' could not be initialized`);
    }
    return tracker;
};

const resolvePageStreamRuntime = (state: BasePageStreamsState): StreamRuntimeOwners => {
    if (!state.coreStreamRuntime) {
        state.coreStreamRuntime = getStreamRuntime();
    }
    return state.coreStreamRuntime;
};

const getOrCreatePageSubscriptionManager = (state: BasePageStreamsState, pageId: string): SubscriptionManager => {
    if (!state.subscriptionManager) {
        state.subscriptionManager = request(subscriptionManager, 'SM').create(pageId);
    }
    return state.subscriptionManager;
};

const cleanupPageStreamsState = async (state: BasePageStreamsState): Promise<void> => {
    if (state.streamTrackers?.size) {
        await Promise.all([...state.streamTrackers.values()].map((tracker) => Promise.resolve(tracker.clear({ abort: true, cancel: false }))));
        state.streamTrackers.clear();
    }
    await state.subscriptionManager?.destroy?.();
    state.subscriptionManager = null;
    state.streamTrackers = null;
};

export { cleanupPageStreamsState, getOrCreatePageStreamTracker, getOrCreatePageSubscriptionManager, resolvePageStreamRuntime };
