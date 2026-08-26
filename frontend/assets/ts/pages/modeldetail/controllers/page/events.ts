/* SoAI - Model detail page control layer events [frontend/assets/ts/pages/modeldetail/controllers/page/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { METRICS, MODELS, PLUGINS } from '@core/realtime/streammanager/resources/ids.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { PageStreamingOwnerHost } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { ModelDetailSession } from '@pages/modeldetail/state/ModelDetailSession.ts';

interface ModelDetailRealtimeDependencies extends PageStreamingOwnerHost, PageResourcesOwnerHost {
    handleModelUpdate: (value: JsonValue | null) => void;
    handleMetricsUpdate: (value: JsonValue | null) => void;
    handlePluginCollectionUpdate: (value: JsonValue | null) => void;
    logRealtimeWarning: (message: string, error: Error) => void;
}

const ensureModelDetailRealtimeCollectionsReady = async (session: ModelDetailSession, host: ModelDetailRealtimeDependencies): Promise<JsonValue | null> => {
    if (!session.realtimeCollectionsInitialized) {
        session.realtimeCollectionsInitialized = true;
        setupModelDetailRealtimeCollectionSubscriptions(host);
    }
    if (!session.realtimeCollectionsReadyPromise) {
        session.realtimeCollectionsReadyPromise = (async () => {
            try {
                await host.streaming.ensureSubscriptions();
                return null;
            } catch (error) {
                const runtimeError = ensureError(error);
                host.logRealtimeWarning('Realtime collection readiness failed', runtimeError);
                session.realtimeCollectionsReadyPromise = null;
                throw runtimeError;
            }
        })();
    }
    return session.realtimeCollectionsReadyPromise;
};

const setupModelDetailRealtimeCollectionSubscriptions = (host: ModelDetailRealtimeDependencies): void => {
    const subscriptions: Array<[string, (value: JsonValue | null) => void]> = [
        [MODELS, (value: JsonValue | null) => host.handleModelUpdate(value)],
        [METRICS, (value: JsonValue | null) => host.handleMetricsUpdate(value)],
        [PLUGINS, (value: JsonValue | null) => host.handlePluginCollectionUpdate(value)]
    ];
    subscriptions.forEach(([resource, handler]: [string, (value: JsonValue | null) => void]) => {
        try {
            const unsubscribe = host.streaming.subscribeResourceValue(resource, handler);
            if (unsubscribe) {
                host.pageResources.track(unsubscribe);
            }
        } catch (error) {
            const runtimeError = ensureError(error);
            host.logRealtimeWarning(`Failed to subscribe to ${resource}`, runtimeError);
        }
    });
};

export { ensureModelDetailRealtimeCollectionsReady, setupModelDetailRealtimeCollectionSubscriptions };
export type { ModelDetailRealtimeDependencies };
