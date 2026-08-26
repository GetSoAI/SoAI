/* SoAI - Plugins feature backend types [frontend/assets/ts/features/plugins/modals/backend/backendTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { StreamActionHandle, StreamHandleTrackerContract } from '@core/routing/pages/pagetypes/public.ts';
import type { StatusInput } from '@core/state/statusTypes.ts';
import type { StreamActionHandlers } from '@core/types/streamTypes.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { OptimisticOperation } from '@core/data/clientdatahub/types.ts';

interface BackendStatusIndicatorApi {
    updateIndicator(element: HTMLElement | null, status: StatusInput): void;
}

interface BackendOperationHost {
    streams: StreamHandleTrackerContract;
    createStreamHandlers: (
        key: string,
        message: string,
        callbacks?: {
            onProgress?: (data: JsonValue | null | undefined) => void;
            onComplete?: (data: JsonValue | null | undefined) => void;
            onError?: (error: Error) => void;
        }
    ) => StreamActionHandlers;
    startTaskAction: (endpoint: string, options: BackendTaskActionOptions, runtimeOptions?: { allowDiscovery?: boolean }) => Promise<StreamActionHandle>;
    startTaskCommand: (command: Record<string, JsonValue | null | undefined>, options: BackendTaskCommandOptions, runtimeOptions?: { allowDiscovery?: boolean }) => Promise<StreamActionHandle>;
    beginOptimisticOperation: (operation: OptimisticOperation) => void;
    formatPluginName: (name: string) => string;
    showNotification: (message: string, type?: NotificationType, duration?: number) => void;
}

interface BackendOperationMeta {
    type: string;
    pluginName?: string;
    plugin?: string;
    displayName?: string;
    message?: string;
    cancelable?: boolean;
    operationKey?: string;
    requestId?: string;
}

interface BackendTaskActionOptions {
    method?: string;
    body?: JsonValue | null | undefined;
    handlers: StreamActionHandlers;
    operation: BackendOperationMeta;
}

interface BackendTaskCommandOptions {
    handlers: StreamActionHandlers;
    operation: BackendOperationMeta;
}

interface BackendManagerSecurity {
    escapeHtml: (value: string | null) => string;
    escapeAttribute: (value: string | null) => string;
}

interface BackendStatuses {
    backendNotInstalled: string;
}
export type { BackendOperationHost, BackendManagerSecurity, BackendStatuses, BackendStatusIndicatorApi, BackendTaskActionOptions, BackendTaskCommandOptions };
