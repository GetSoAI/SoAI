/* SoAI - WebSocket resource push epoch ordering [frontend/assets/ts/core/realtime/streammanager/resources/resourcePushOrdering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PushCommitContext } from '@core/realtime/streammanager/resources/resourceReconciliationTypes.ts';

class ResourcePushOrdering {
    #transportEpoch = 0;
    #remoteTimestampWatermarkMs: number | null = null;

    accepts(context: PushCommitContext, currentTransportEpoch: number, currentReceiveSequence: number): boolean {
        if (context.transportEpoch < currentTransportEpoch) return false;
        if (context.transportEpoch === currentTransportEpoch && context.receiveSequence <= currentReceiveSequence) return false;
        if (context.transportEpoch === this.#transportEpoch && context.remoteTimestampMs !== null && this.#remoteTimestampWatermarkMs !== null && context.remoteTimestampMs < this.#remoteTimestampWatermarkMs) return false;
        return true;
    }

    record(context: PushCommitContext): void {
        if (context.transportEpoch !== this.#transportEpoch) {
            this.#transportEpoch = context.transportEpoch;
            this.#remoteTimestampWatermarkMs = null;
        }
        if (context.remoteTimestampMs !== null) this.#remoteTimestampWatermarkMs = context.remoteTimestampMs;
    }
}

export { ResourcePushOrdering };
