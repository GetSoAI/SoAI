/* SoAI - Frontend scoped raw response body ownership [frontend/assets/ts/core/api/scopedRawResponse.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiAbortScope } from '@core/api/abortScope.ts';
import { APIError } from '@core/apiError.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';

interface ScopedRawResponseDependencies {
    registerNetworkError(): void;
}

class ScopedRawResponse extends Response {
    readonly #upstreamResponse: Response;

    constructor(body: ReadableStream<Uint8Array>, upstreamResponse: Response) {
        super(body, {
            status: upstreamResponse.status,
            statusText: upstreamResponse.statusText,
            headers: upstreamResponse.headers
        });
        this.#upstreamResponse = upstreamResponse;
    }

    override get redirected(): boolean {
        return this.#upstreamResponse.redirected;
    }

    override get type(): ResponseType {
        return this.#upstreamResponse.type;
    }

    override get url(): string {
        return this.#upstreamResponse.url;
    }
}

const buildAbortError = (scope: ApiAbortScope): APIError => {
    const error = new APIError(0, scope.timeoutTriggered ? 'Request timed out' : 'Request aborted');
    if (!scope.timeoutTriggered) {
        error.name = 'AbortError';
    }
    return error;
};

const buildBodyReadError = (error: Error): APIError => new APIError(0, error.message || 'Network request failed', { cause: error });

const createScopedRawResponse = (response: Response, scope: ApiAbortScope, dependencies: ScopedRawResponseDependencies): Response => {
    if (response.body === null) {
        scope.cleanup();
        return response;
    }
    const upstreamReader = response.body.getReader();
    let controller: ReadableStreamDefaultController<Uint8Array> | null = null;
    let terminal = false;
    let failureReported = false;
    const finish = (): void => {
        if (terminal) {
            return;
        }
        terminal = true;
        scope.signal.removeEventListener('abort', handleAbort);
        scope.cleanup();
    };
    const reportNetworkFailure = (): void => {
        if (failureReported) {
            return;
        }
        failureReported = true;
        dependencies.registerNetworkError();
    };
    const cancelUpstream = (reason: APIError): void => {
        void upstreamReader.cancel(reason).catch((error) => {
            errorHandler.debug('ApiClient', 'Raw response reader cancellation failed', ensureError(error));
        });
    };
    const handleAbort = (): void => {
        if (terminal) {
            return;
        }
        const error = buildAbortError(scope);
        if (scope.timeoutTriggered) {
            reportNetworkFailure();
        }
        cancelUpstream(error);
        controller?.error(error);
        finish();
    };
    const body = new ReadableStream<Uint8Array>({
        start(streamController): void {
            controller = streamController;
            scope.signal.addEventListener('abort', handleAbort, { once: true });
            if (scope.signal.aborted) {
                handleAbort();
            }
        },
        async pull(streamController): Promise<void> {
            if (terminal) {
                return;
            }
            try {
                const result = await upstreamReader.read();
                if (terminal) {
                    return;
                }
                if (scope.signal.aborted) {
                    handleAbort();
                    return;
                }
                if (result.done) {
                    streamController.close();
                    finish();
                    return;
                }
                streamController.enqueue(result.value);
            } catch (error) {
                if (terminal) {
                    return;
                }
                if (scope.signal.aborted) {
                    handleAbort();
                    return;
                }
                reportNetworkFailure();
                streamController.error(buildBodyReadError(ensureError(error)));
                finish();
            }
        },
        async cancel(reason): Promise<void> {
            if (terminal) {
                return;
            }
            finish();
            await upstreamReader.cancel(reason);
        }
    });
    return new ScopedRawResponse(body, response);
};

export { createScopedRawResponse };
