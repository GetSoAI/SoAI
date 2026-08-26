/* SoAI - WebSocket reconnect attempt and timer ownership [frontend/assets/ts/core/websocketclient/WebSocketReconnectScheduler.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';
import { calculateReconnectDelay } from '@core/websocketclient/effects.ts';

type WebSocketReconnectPlan = { status: 'blocked' } | { status: 'scheduled'; attempt: number; delay: number };

interface WebSocketReconnectDependencies {
    isBlocked: () => boolean;
    reconnect: () => void;
    log: (level: 'debug' | 'warn' | 'error', message: string) => void;
    emit: (stage: string, data?: JsonObject, severity?: 'info' | 'warn' | 'error') => void;
}

const shouldReportReconnectAttempt = (attempt: number): boolean => attempt <= 3 || attempt % 20 === 0;

class WebSocketReconnectScheduler {
    readonly #dependencies: WebSocketReconnectDependencies;
    #attempts = 0;
    #timer: ReturnType<typeof setTimeout> | null = null;

    constructor(dependencies: WebSocketReconnectDependencies) {
        this.#dependencies = dependencies;
    }

    get attempts(): number {
        return this.#attempts;
    }

    reset(): void {
        this.cancel();
        this.#attempts = 0;
    }

    cancel(): void {
        if (this.#timer === null) return;
        clearTimeout(this.#timer);
        this.#timer = null;
    }

    schedule(): WebSocketReconnectPlan {
        if (this.#dependencies.isBlocked()) return { status: 'blocked' };
        const delay = calculateReconnectDelay(this.#attempts);
        const attempt = this.#attempts + 1;
        if (shouldReportReconnectAttempt(attempt)) {
            const isInitialAttempt = attempt <= 3;
            this.#dependencies.log(isInitialAttempt ? 'debug' : 'warn', `Scheduling reconnect attempt ${attempt} in ${delay}ms`);
            this.#dependencies.emit(isInitialAttempt ? 'reconnect:scheduled' : 'reconnect:supervising', { attempt, delay }, isInitialAttempt ? 'info' : 'warn');
        }
        this.cancel();
        this.#timer = setTimeout(() => {
            this.#timer = null;
            if (this.#dependencies.isBlocked()) return;
            this.#attempts = attempt;
            this.#dependencies.reconnect();
        }, delay);
        return { status: 'scheduled', attempt, delay };
    }
}

export { WebSocketReconnectScheduler };
export { shouldReportReconnectAttempt };
export type { WebSocketReconnectDependencies, WebSocketReconnectPlan };
