/* SoAI - Shared OpenAI model test stream client [frontend/assets/ts/core/openai/modelTestStreamClient.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import { runCleanup } from '@core/lifecycle/cleanup.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { getWebSocketClient } from '@core/websocketclient/service.ts';
import { WEBSOCKET_EVENT_TYPES, WEBSOCKET_MESSAGE_TYPES } from '@core/websocketEvents.ts';
import { readModelTestDeltaText, readModelTestErrorMessage, readModelTestEventType, readModelTestRunId, readModelTestSequence } from '@core/openai/modelTestStreamParsing.ts';

interface ModelTestStreamMessage {
    role: 'user' | 'assistant' | 'system' | 'tool';
    content: string;
}

interface ModelTestStreamRequest {
    model: string;
    messages: ModelTestStreamMessage[];
    stream: true;
    reasoningEffort?: string;
}

type ModelTestStreamRunOptions = {
    runId: string;
    request: ModelTestStreamRequest;
    signal: AbortSignal;
    cancelReason: string;
    isActive?: (() => boolean) | undefined;
    errorMessageFallback: string;
    onAssistantTextDelta: (delta: string) => void;
};

const serializeModelTestOpenAiRequest = (request: ModelTestStreamRequest): JsonObject => {
    const serialized: JsonObject = {
        model: request.model,
        messages: request.messages.map((message) => ({ role: message.role, content: message.content })),
        stream: request.stream
    };
    if (request.reasoningEffort !== undefined) serialized['reasoning_effort'] = request.reasoningEffort;
    return serialized;
};

const serializeModelTestCancel = (runId: string, reason: string): JsonObject => ({
    type: WEBSOCKET_MESSAGE_TYPES.MODEL_TEST_STREAM_CANCEL,
    'run_id': runId,
    reason
});

const serializeModelTestStart = (runId: string, request: ModelTestStreamRequest): JsonObject => ({
    type: WEBSOCKET_MESSAGE_TYPES.MODEL_TEST_STREAM_START,
    'run_id': runId,
    'openai_request': serializeModelTestOpenAiRequest(request)
});

const sendModelTestStreamCancel = async (runId: string, reason: string): Promise<void> => {
    const normalizedRunId = runId.trim();
    const normalizedReason = reason.trim();
    if (!normalizedRunId || !normalizedReason) {
        return;
    }
    const client = getWebSocketClient();
    await client.sendMessage(serializeModelTestCancel(normalizedRunId, normalizedReason));
};

const runOpenAiModelTestStream = async (options: ModelTestStreamRunOptions): Promise<void> => {
    if (options.signal.aborted) {
        throw new Error('Model test stream aborted before starting');
    }
    const client = getWebSocketClient();
    client.connect();
    await client.waitForConnection(undefined, { signal: options.signal });
    throwIfAborted(options.signal);

    let lastSequence = -1;
    const completion = createDeferred<void>();
    let unsubscribe: (() => void) | null = null;

    const cleanup = (abortListener: (() => void) | null): void => {
        const dispose = unsubscribe;
        unsubscribe = null;
        runCleanup(dispose, (runtimeError) => {
            errorHandler.warn('ModelTestStream', 'Model test stream cleanup failed', runtimeError);
        });
        if (abortListener) {
            options.signal.removeEventListener('abort', abortListener);
        }
    };

    const abortListener = (): void => {
        void sendModelTestStreamCancel(options.runId, options.cancelReason).catch((error) => {
            errorHandler.warn('ModelTestStream', 'Model test stream cancellation failed', ensureError(error));
        });
        cleanup(abortListener);
        completion.reject(new Error('Model test stream aborted'));
    };

    const onEvent = (payload: JsonValue): void => {
        if (options.isActive && !options.isActive()) {
            return;
        }
        const runId = readModelTestRunId(payload);
        if (!runId || runId !== options.runId) {
            return;
        }
        const sequence = readModelTestSequence(payload);
        if (sequence === null) {
            cleanup(abortListener);
            completion.reject(new Error('Model test stream event is missing a sequence'));
            return;
        }
        if (sequence <= lastSequence) {
            return;
        }
        if (sequence !== lastSequence + 1) {
            cleanup(abortListener);
            completion.reject(new Error(`Model test stream sequence gap: expected ${String(lastSequence + 1)}, received ${String(sequence)}`));
            return;
        }
        lastSequence = sequence;

        const eventType = readModelTestEventType(payload);
        if (!eventType) {
            cleanup(abortListener);
            completion.reject(new Error('Model test stream event is missing its event type'));
            return;
        }
        if (eventType === 'loading') {
            return;
        }
        if (eventType === 'assistant_text_delta') {
            const delta = readModelTestDeltaText(payload);
            if (!delta) {
                cleanup(abortListener);
                completion.reject(new Error('Model test stream text delta is empty'));
                return;
            }
            options.onAssistantTextDelta(delta);
            return;
        }
        if (eventType === 'completed') {
            cleanup(abortListener);
            completion.resolve();
            return;
        }
        if (eventType === 'error') {
            cleanup(abortListener);
            completion.reject(new Error(readModelTestErrorMessage(payload) || options.errorMessageFallback));
            return;
        }
        cleanup(abortListener);
        completion.reject(new Error(`Unsupported model test stream event type: ${eventType}`));
    };

    try {
        unsubscribe = client.subscribe(WEBSOCKET_EVENT_TYPES.MODEL_TEST_STREAM_EVENT, onEvent);
        options.signal.addEventListener('abort', abortListener, { once: true });
        throwIfAborted(options.signal);
        await client.sendMessage(serializeModelTestStart(options.runId, options.request), { signal: options.signal });
        await completion.promise;
    } catch (error) {
        cleanup(abortListener);
        throw ensureError(error);
    }
};

export { runOpenAiModelTestStream };
export type { ModelTestStreamRequest, ModelTestStreamRunOptions };
