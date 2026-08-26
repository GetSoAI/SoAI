/* SoAI - Shared routing base page streams actions [frontend/assets/ts/core/routing/pages/basepagestreams/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { StreamActionHandlers, StreamHandlerCallbacks } from '@core/routing/pages/basepagestreams/internalContracts.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

const createStreamHandlers = ({ onProgress, onComplete, onError }: StreamHandlerCallbacks = {}): StreamActionHandlers => {
    const handlers: StreamActionHandlers = {};
    if (typeof onProgress === 'function') {
        handlers.onUpdate = (data: JsonValue | null) => onProgress(data);
        handlers.onProgress = (data: JsonValue | null) => onProgress(data);
    }
    if (typeof onComplete === 'function') {
        handlers.onComplete = (data: JsonValue | null) => onComplete(data);
    }
    if (typeof onError === 'function') {
        handlers.onStreamError = (data: JsonValue | null) => onError(data);
        handlers.onError = (error: Error) => onError(error);
    }
    return handlers;
};

export { createStreamHandlers };
