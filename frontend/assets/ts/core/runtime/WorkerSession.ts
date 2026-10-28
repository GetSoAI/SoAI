/* SoAI - Validated worker startup and connection lifetime [frontend/assets/ts/core/runtime/WorkerSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createDeferred } from '@core/runtime/deferred.ts';
import { TimeoutTimer } from '@core/timers/timeoutTimer.ts';
import { createAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

interface WorkerSessionOptions<Response> {
    createWorker: () => Worker;
    decode: (value: JsonValue | null | undefined) => Response;
    isReady: (response: Response) => boolean;
    onMessage: (response: Response) => void;
    onFailure: (error: Error, wasReady: boolean) => void;
    timeoutMs: number;
    label: string;
}

type WorkerSessionState = { type: 'starting' } | { type: 'ready' } | { type: 'closed'; error: Error };

class WorkerSession<Request extends { type: string }, Response> {
    readonly #worker: Worker;
    readonly #options: WorkerSessionOptions<Response>;
    readonly #completion = createDeferred<void>();
    readonly #deadline: TimeoutTimer;
    #state: WorkerSessionState = { type: 'starting' };

    constructor(options: WorkerSessionOptions<Response>) {
        this.#options = options;
        this.#worker = options.createWorker();
        this.#deadline = new TimeoutTimer(options.timeoutMs, () => this.#fail(new Error(`${options.label} bootstrap timed out`)));
        this.#worker.onmessage = this.#receive;
        this.#worker.onerror = this.#crash;
        this.#worker.onmessageerror = () => this.#fail(new Error(`${options.label} returned an undecodable message`));
        this.#deadline.start();
    }

    get ready(): Promise<void> {
        return this.#completion.promise;
    }

    get isReady(): boolean {
        return this.#state.type === 'ready';
    }

    postMessage(request: Request, transfer: Transferable[] = []): void {
        if (this.#state.type === 'closed') throw this.#state.error;
        this.#worker.postMessage(request, transfer);
    }

    #receive = (event: MessageEvent<JsonValue | null | undefined>): void => {
        if (this.#state.type === 'closed') return;
        try {
            const response = this.#options.decode(event.data);
            if (this.#options.isReady(response)) {
                if (this.#state.type === 'starting') {
                    this.#state = { type: 'ready' };
                    this.#deadline.stop();
                    this.#completion.resolve();
                }
                return;
            }
            this.#options.onMessage(response);
        } catch (error) {
            this.#fail(ensureError(error));
        }
    };

    #crash = (event: ErrorEvent): void => {
        const location = event.filename ? `${event.filename}${event.lineno || event.colno ? `:${event.lineno}:${event.colno}` : ''}` : '';
        const details = [event.message, location].filter(Boolean).join(' | ');
        this.#fail(new Error(`${this.#options.label} crashed${details ? `: ${details}` : ''}`));
    };

    #fail(error: Error): void {
        if (this.#state.type === 'closed') return;
        const wasReady = this.isReady;
        this.dispose(error);
        this.#options.onFailure(error, wasReady);
    }

    dispose(error: Error = createAbortError('Worker session disposed')): void {
        if (this.#state.type === 'closed') return;
        const wasStarting = this.#state.type === 'starting';
        this.#state = { type: 'closed', error };
        this.#deadline.stop();
        this.#worker.onmessage = null;
        this.#worker.onerror = null;
        this.#worker.onmessageerror = null;
        this.#worker.terminate();
        if (wasStarting) this.#completion.reject(error);
    }
}

export { WorkerSession };
