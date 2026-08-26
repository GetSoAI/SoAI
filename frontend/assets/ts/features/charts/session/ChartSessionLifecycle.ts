/* SoAI - Chart session transactional lifecycle [frontend/assets/ts/features/charts/session/ChartSessionLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { isString } from '@core/typeGuards.ts';

type ChartLifecycleState = 'created' | 'initializing' | 'ready' | 'destroying' | 'destroyed';

interface ChartLifecycleStep {
    initialize(signal: AbortSignal): void | Promise<void>;
    destroy(): void | Promise<void>;
}

interface ChartLifecycleDependencies {
    events: ChartLifecycleStep;
    redraw: ChartLifecycleStep;
    surface: ChartLifecycleStep;
    theme: ChartLifecycleStep;
    loading: ChartLifecycleStep;
    viewportResize: ChartLifecycleStep;
    renderer: ChartLifecycleStep;
    interaction: ChartLifecycleStep;
}

const normalizeLifecycleError = <TValue>(value: TValue): Error => {
    const error = ensureError(value);
    if (typeof value === 'object' && value !== null && 'name' in value && isString(value.name) && value.name) error.name = value.name;
    return error;
};

const resolveLifecycleOperation = async (): Promise<void> => {};

const rejectLifecycleOperation = async (error: Error): Promise<void> => {
    throw error;
};

class ChartSessionLifecycle {
    readonly #steps: readonly ChartLifecycleStep[];
    readonly #controller = new AbortController();
    readonly #initialized = new Set<ChartLifecycleStep>();
    #state: ChartLifecycleState = 'created';
    #initialization: Promise<void> | null = null;
    #destruction: Promise<void> | null = null;

    constructor({ events, redraw, surface, theme, loading, viewportResize, renderer, interaction }: ChartLifecycleDependencies) {
        this.#steps = [events, redraw, surface, theme, loading, viewportResize, renderer, interaction];
    }

    get state(): ChartLifecycleState {
        return this.#state;
    }

    initialize({ signal }: { signal?: AbortSignal } = {}): Promise<void> {
        if (this.#state === 'destroyed' || this.#state === 'destroying') return rejectLifecycleOperation(new Error('Cannot initialize a destroyed chart session'));
        if (this.#state === 'ready') return resolveLifecycleOperation();
        if (this.#initialization) return this.#initialization;
        if (signal?.aborted) {
            this.#state = 'destroyed';
            return rejectLifecycleOperation(normalizeLifecycleError(signal.reason ?? new DOMException('Chart initialization aborted', 'AbortError')));
        }
        const unlink = this.#linkAbortSignal(signal);
        this.#state = 'initializing';
        this.#initialization = this.#runInitialization().finally(() => {
            unlink();
            this.#initialization = null;
        });
        return this.#initialization;
    }

    destroy(): Promise<void> {
        if (this.#state === 'destroyed') return resolveLifecycleOperation();
        if (this.#destruction) return this.#destruction;
        this.#state = 'destroying';
        this.#controller.abort(new DOMException('Chart session destroyed', 'AbortError'));
        this.#destruction = this.#runDestruction().finally(() => {
            this.#state = 'destroyed';
            this.#destruction = null;
        });
        return this.#destruction;
    }

    async #runInitialization(): Promise<void> {
        try {
            for (const step of this.#steps) {
                this.#controller.signal.throwIfAborted();
                await step.initialize(this.#controller.signal);
                this.#initialized.add(step);
            }
            this.#controller.signal.throwIfAborted();
            this.#state = 'ready';
        } catch (error) {
            const initializationError = normalizeLifecycleError(error);
            const cleanupErrors = await this.#cleanupInitialized();
            this.#state = 'destroyed';
            if (cleanupErrors.length > 0) throw new AggregateError([initializationError, ...cleanupErrors], 'Chart initialization and rollback failed');
            throw initializationError;
        }
    }

    async #runDestruction(): Promise<void> {
        if (this.#initialization) {
            try {
                await this.#initialization;
            } catch (error) {
                const initializationError = normalizeLifecycleError(error);
                if (initializationError.name === 'AbortError') return;
                throw initializationError;
            }
        }
        const errors = await this.#cleanupInitialized();
        if (errors.length > 0) throw new AggregateError(errors, 'Chart destruction failed');
    }

    async #cleanupInitialized(): Promise<Error[]> {
        const errors: Error[] = [];
        for (const step of [...this.#steps].reverse()) {
            if (!this.#initialized.delete(step)) continue;
            try {
                await step.destroy();
            } catch (error) {
                errors.push(normalizeLifecycleError(ensureError(error)));
            }
        }
        return errors;
    }

    #linkAbortSignal(signal: AbortSignal | undefined): () => void {
        if (!signal) return () => undefined;
        const abort = (): void => this.#controller.abort(signal.reason ?? new DOMException('Chart initialization aborted', 'AbortError'));
        signal.addEventListener('abort', abort, { once: true });
        return () => signal.removeEventListener('abort', abort);
    }
}

export { ChartSessionLifecycle };
export type { ChartLifecycleDependencies, ChartLifecycleState, ChartLifecycleStep };
