/* SoAI - Dashboard page logs effects [frontend/assets/ts/pages/dashboard/widgets/logs/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { CORE_LOG_SOURCE } from '@features/logging/public.ts';
import type { DashboardLogsHost, DashboardLogStream, DashboardLogStreamHandler } from '@pages/dashboard/widgets/logs/types.ts';

interface DashboardLogsStreamDependencies {
    host: DashboardLogsHost;
    getReplayLimit: () => number;
    onStreamEvent: DashboardLogStreamHandler;
}

class DashboardLogsStreamController {
    readonly #host: DashboardLogsHost;
    readonly #getReplayLimit: () => number;
    readonly #onStreamEvent: DashboardLogStreamHandler;
    readonly #activationToken = new SequenceToken();
    #streamUnsubscribe: (() => void) | null = null;
    #activationPromise: Promise<void> | null = null;

    constructor(dependencies: DashboardLogsStreamDependencies) {
        this.#host = dependencies.host;
        this.#getReplayLimit = dependencies.getReplayLimit;
        this.#onStreamEvent = dependencies.onStreamEvent;
    }

    activate(): Promise<void> {
        if (this.#activationPromise) {
            return this.#activationPromise;
        }
        if (this.#streamUnsubscribe) {
            return (async (): Promise<void> => undefined)();
        }
        if (this.#host.isDestroyed()) {
            return (async (): Promise<void> => undefined)();
        }

        const token = this.#activationToken.next();
        const ready = (async (): Promise<void> => {
            try {
                const stream: DashboardLogStream = await this.#host.ensureLogStreamReady();
                if (this.#host.isDestroyed() || !this.#activationToken.isActive(token)) {
                    return;
                }
                const unsubscribe: () => void = stream.subscribe(this.#onStreamEvent, {
                    replayLimit: this.#getReplayLimit(),
                    source: CORE_LOG_SOURCE
                });
                if (this.#host.isDestroyed() || !this.#activationToken.isActive(token)) {
                    unsubscribe();
                    return;
                }
                this.#clearStreamSubscription();
                this.#streamUnsubscribe = unsubscribe;
            } catch (error) {
                const normalized = ensureError(error);
                this.#host.logError('Dashboard logs activation failed', normalized);
                throw normalized;
            } finally {
                if (this.#activationToken.isActive(token)) {
                    this.#activationPromise = null;
                }
            }
        })();

        this.#activationPromise = ready;
        return ready;
    }

    deactivate(): void {
        this.#activationToken.invalidate();
        this.#activationPromise = null;
        this.#clearStreamSubscription();
    }

    #clearStreamSubscription(): void {
        if (!this.#streamUnsubscribe) {
            return;
        }
        try {
            this.#streamUnsubscribe();
        } catch (error) {
            const normalized = ensureError(error);
            this.#host.logError('Dashboard logs unsubscribe failed', normalized);
        }
        this.#streamUnsubscribe = null;
    }
}

export { DashboardLogsStreamController };
