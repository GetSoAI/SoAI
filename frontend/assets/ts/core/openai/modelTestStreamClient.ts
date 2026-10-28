/* SoAI - Shared OpenAI model test stream client [frontend/assets/ts/core/openai/modelTestStreamClient.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { createAbortSignalScope, raceWithAbortSignal, throwIfAborted } from '@core/errors/abort.ts';
import { runCleanup } from '@core/lifecycle/cleanup.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { TimeoutTimer } from '@core/timers/timeoutTimer.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { getWebSocketClient } from '@core/websocketclient/service.ts';
import { WEBSOCKET_EVENT_TYPES, WEBSOCKET_LIFECYCLE_EVENT_TYPES, WEBSOCKET_MESSAGE_TYPES } from '@core/websocketEvents.ts';
import { ModelTestStreamError, normalizeModelTestFailureMetadata, readModelTestStreamResult, type ModelTestStreamFailureOutcome, type ModelTestStreamResult } from '@core/openai/modelTestStreamOutcome.ts';
import { readModelTestErrorCode, readModelTestDeltaText, readModelTestErrorMessage, readModelTestEventType, readModelTestRunId, readModelTestSequence } from '@core/openai/modelTestStreamParsing.ts';

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
    timeoutMs?: number | undefined;
    loadingTimeoutMs?: number | undefined;
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

const runOpenAiModelTestStream = async (options: ModelTestStreamRunOptions): Promise<ModelTestStreamResult> => {
    if (options.signal.aborted) {
        throw new ModelTestStreamError('Model test stream aborted before starting', 'cancelled');
    }
    const client = getWebSocketClient();
    client.connect();
    try {
        await client.waitForConnection(undefined, { signal: options.signal });
        throwIfAborted(options.signal);
    } catch (error) {
        throw new ModelTestStreamError(ensureError(error).message, options.signal.aborted ? 'cancelled' : 'disconnected');
    }

    let lastSequence = -1;
    let visibleText = '';
    const completion = createDeferred<ModelTestStreamResult>();
    const unsubscribers: (() => void)[] = [];
    let settled = false;
    let generationStarted = false;
    const transportController = new AbortController();
    const transportScope = createAbortSignalScope([options.signal, transportController.signal]);
    const timeout = new TimeoutTimer(0, () => {
        cancelRemoteRun();
        fail(new Error('Model test stream timed out'), 'timeout');
    });

    const cleanup = (): void => {
        settled = true;
        transportController.abort();
        transportScope.cleanup();
        timeout.stop();
        for (const dispose of unsubscribers.splice(0)) {
            runCleanup(dispose, (runtimeError) => {
                errorHandler.warn('ModelTestStream', 'Model test stream cleanup failed', runtimeError);
            });
        }
        options.signal.removeEventListener('abort', abortListener);
    };

    const fail = (error: Error, outcome: ModelTestStreamFailureOutcome): void => {
        if (settled) return;
        cleanup();
        completion.reject(new ModelTestStreamError(error.message, outcome, error instanceof ModelTestStreamError ? error.failure : normalizeModelTestFailureMetadata(null, options.runId)));
    };

    const cancelRemoteRun = (): void => {
        void sendModelTestStreamCancel(options.runId, options.cancelReason).catch((error) => {
            errorHandler.warn('ModelTestStream', 'Model test stream cancellation failed', ensureError(error));
        });
    };

    const abortListener = (): void => {
        cancelRemoteRun();
        fail(new Error('Model test stream aborted'), 'cancelled');
    };

    const onEvent = (payload: JsonValue): void => {
        if (settled) return;
        if (options.isActive && !options.isActive()) {
            return;
        }
        const runId = readModelTestRunId(payload);
        if (!runId || runId !== options.runId) {
            return;
        }
        const sequence = readModelTestSequence(payload);
        if (sequence === null) {
            fail(new Error('Model test stream event is missing a sequence'), 'disconnected');
            return;
        }
        if (sequence <= lastSequence) {
            return;
        }
        if (sequence !== lastSequence + 1) {
            fail(new Error(`Model test stream sequence gap: expected ${String(lastSequence + 1)}, received ${String(sequence)}`), 'disconnected');
            return;
        }
        lastSequence = sequence;

        const eventType = readModelTestEventType(payload);
        if (!eventType) {
            fail(new Error('Model test stream event is missing its event type'), 'disconnected');
            return;
        }
        if (eventType === 'loading') {
            return;
        }
        if (eventType === 'assistant_text_delta') {
            const delta = readModelTestDeltaText(payload);
            if (!delta) {
                fail(new Error('Model test stream text delta is empty'), 'disconnected');
                return;
            }
            visibleText += delta;
            if (!generationStarted && options.loadingTimeoutMs !== undefined) {
                generationStarted = true;
                timeout.stop();
                if (options.timeoutMs !== undefined) timeout.start(options.timeoutMs);
            }
            options.onAssistantTextDelta(delta);
            return;
        }
        if (eventType === 'completed') {
            cleanup();
            completion.resolve(readModelTestStreamResult(visibleText));
            return;
        }
        if (eventType === 'error') {
            fail(new ModelTestStreamError(readModelTestErrorMessage(payload) || options.errorMessageFallback, 'load_error', normalizeModelTestFailureMetadata(readModelTestErrorCode(payload), runId)), 'load_error');
            return;
        }
        fail(new Error(`Unsupported model test stream event type: ${eventType}`), 'load_error');
    };

    try {
        unsubscribers.push(client.subscribe(WEBSOCKET_EVENT_TYPES.MODEL_TEST_STREAM_EVENT, onEvent));
        unsubscribers.push(client.subscribe(WEBSOCKET_LIFECYCLE_EVENT_TYPES.DISCONNECTED, () => fail(new Error('Model test stream connection was lost'), 'disconnected')));
        options.signal.addEventListener('abort', abortListener, { once: true });
        throwIfAborted(options.signal);
        const initialTimeoutMs = options.loadingTimeoutMs ?? options.timeoutMs;
        if (initialTimeoutMs !== undefined) timeout.start(initialTimeoutMs);
        await raceWithAbortSignal(client.sendMessage(serializeModelTestStart(options.runId, options.request), { signal: transportScope.signal }), transportScope.signal);
    } catch (error) {
        fail(ensureError(error), options.signal.aborted ? 'cancelled' : 'disconnected');
    }
    return completion.promise;
};

export { runOpenAiModelTestStream };
export type { ModelTestStreamRequest, ModelTestStreamRunOptions };
