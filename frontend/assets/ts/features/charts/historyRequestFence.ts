/* SoAI - Charts feature history request fence [frontend/assets/ts/features/charts/historyRequestFence.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SequenceToken } from '@core/concurrency/sequenceToken.ts';

interface HistoryRequestLease {
    readonly generation: number;
    readonly signal: AbortSignal;
}

class HistoryRequestFence {
    readonly #generation = new SequenceToken();
    #controller: AbortController | null = null;

    begin(): HistoryRequestLease {
        this.invalidate();
        const controller = new AbortController();
        this.#controller = controller;
        return { generation: this.#generation.value, signal: controller.signal };
    }

    current(): HistoryRequestLease | null {
        const controller = this.#controller;
        return controller ? { generation: this.#generation.value, signal: controller.signal } : null;
    }

    isCurrent(lease: HistoryRequestLease): boolean {
        return this.#generation.isActive(lease.generation) && !lease.signal.aborted;
    }

    invalidate(): void {
        this.#generation.invalidate();
        const controller = this.#controller;
        this.#controller = null;
        controller?.abort();
    }
}

export { HistoryRequestFence };
export type { HistoryRequestLease };
