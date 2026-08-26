/* SoAI - Shared routing internal contracts [frontend/assets/ts/core/routing/pages/basepagestreams/internalContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { StreamRuntimeOwners } from '@core/realtime/streammanager/public.ts';
import type { OperationEvent } from '@core/realtime/streammanager/types.ts';
import type { StreamHandleTracker } from '@core/routing/pages/pageStreams.ts';
import type { PageAutoResourceState, RunPageTaskOptions, StreamHandlerCallbacks, SubscriptionManager } from '@core/routing/pages/pagetypes/public.ts';
import type { StreamActionHandlers } from '@core/types/streamTypes.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

interface BasePageStreamsState {
    streamTrackers: Map<string, StreamHandleTracker> | null;
    coreStreamRuntime: StreamRuntimeOwners | null;
    subscriptionManager: SubscriptionManager | null;
    autoResourceCleanup: (() => void) | null;
    autoResourceOfflineVisible: boolean;
}

interface BasePageStreamsTaskHost {
    pageId: string;
    setLoadingState: (element: Element | string, loading: boolean, text?: string) => void;
    showNotification: (message: string, type: NotificationType) => void;
    pageContext: {
        telemetry?: {
            emit?: (payload: { severity: string; module: string; message: string; stage: string; tags: string[]; context: JsonObject; duration?: number; data?: JsonObject }) => void;
        };
    };
}

interface EnsureReadyStreamManager {
    ensureReady: (options: { allowDiscovery: boolean; signal?: AbortSignal | undefined }) => Promise<void> | void;
}

interface OperationsSubscriptionManager {
    subscribeOperations: (handler: (eventObject: OperationEvent) => void) => (() => void) | null;
}

interface VerifiableSubscriptionManager {
    verifyReady: () => Promise<void> | void;
}

interface BasePageStreamsAutoResourceResult {
    state: PageAutoResourceState | null;
    shouldShowOfflineBanner: boolean;
    shouldClearOfflineBanner: boolean;
    message: string | null;
}

interface BasePageStreamsTaskTelemetryContext {
    context: JsonObject;
    tags: string[];
    label: string;
}

export type { BasePageStreamsAutoResourceResult, BasePageStreamsState, BasePageStreamsTaskHost, BasePageStreamsTaskTelemetryContext, EnsureReadyStreamManager, OperationsSubscriptionManager, PageAutoResourceState, RunPageTaskOptions, StreamActionHandlers, StreamHandlerCallbacks, SubscriptionManager, VerifiableSubscriptionManager };
