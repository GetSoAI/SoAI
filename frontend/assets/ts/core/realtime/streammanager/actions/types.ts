/* SoAI - Shared frontend realtime stream manager actions public contracts [frontend/assets/ts/core/realtime/streammanager/actions/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiServiceInterface, OperationMetadata, StreamSafeCallback, StreamSafeCallbackArgument } from '@core/realtime/streammanager/types.ts';
import type { ApiRequestBody } from '@core/api/types/request.ts';
import type { StreamActionHandlers } from '@core/types/streamTypes.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

interface StreamTaskRuntimeWebSocketClient {
    connect: () => void;
    waitForConnection: () => Promise<void>;
    requestSnapshot: (resource: string, parameters?: JsonObject) => Promise<{ data?: JsonValue } | null>;
    sendMessage: (payload: JsonObject) => Promise<void>;
    subscribeAll: (handler: (eventType: string, payload: JsonValue) => void | Promise<void>) => () => void;
}

interface StreamTaskRequestOptions {
    method: string;
    body: ApiRequestBody;
    headers: Record<string, string>;
    allowDiscovery?: boolean;
}

type StreamTaskRequest = (endpoint: string, options: StreamTaskRequestOptions) => Promise<Response | null>;
type StreamTaskWebSocketProvider = () => StreamTaskRuntimeWebSocketClient | null;
type StreamTaskSafeInvoker = (callback: StreamSafeCallback | null | undefined, ...inputArguments: StreamSafeCallbackArgument[]) => void;

interface StreamTaskRuntimeOptions {
    module: string;
    eventTarget: EventTarget;
    apiClient: ApiServiceInterface;
    request: StreamTaskRequest;
    getWebSocket: StreamTaskWebSocketProvider;
    safe: StreamTaskSafeInvoker;
}

interface StreamTaskActionPayload {
    method?: string;
    body?: ApiRequestBody;
    headers?: Record<string, string>;
    handlers?: StreamActionHandlers;
    operation?: Partial<OperationMetadata> | null;
    allowDiscovery?: boolean;
    timeoutMs?: number;
}

type StreamTaskDebugLogger = (module: string, message: string, error: Error) => void;

export type { StreamTaskRequest, StreamTaskSafeInvoker, StreamTaskWebSocketProvider, StreamTaskRuntimeOptions, StreamTaskActionPayload, StreamTaskDebugLogger };
export type { StreamTaskRuntimeWebSocketClient };
