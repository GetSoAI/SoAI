/* SoAI - Frontend terminal PTY handshake event buffer [frontend/assets/ts/features/terminal/ptyTerminalEventBuffer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PtyBusyEvent, PtyExitedEvent, PtyOutputEvent } from '@core/realtime/eventcontracts/terminalContracts.ts';

const MAX_BUFFERED_PTY_EVENTS = 128;

type BufferedPtyEvent = { type: 'output'; payload: PtyOutputEvent } | { type: 'exited'; payload: PtyExitedEvent } | { type: 'busy'; payload: PtyBusyEvent };

type BufferedPtyEventHandlers = {
    onOutput: (payload: PtyOutputEvent) => void;
    onExited: (payload: PtyExitedEvent) => void;
    onBusy: (payload: PtyBusyEvent) => void;
};

class PtyTerminalEventBuffer {
    readonly #events: Array<BufferedPtyEvent> = [];
    #activeGeneration: number | null = null;

    start(generation: number): void {
        this.#events.length = 0;
        this.#activeGeneration = generation;
    }

    clear(): void {
        this.#events.length = 0;
        this.#activeGeneration = null;
    }

    push(event: BufferedPtyEvent, generation: number): boolean {
        if (this.#activeGeneration !== generation) return false;
        if (this.#events.length >= MAX_BUFFERED_PTY_EVENTS) {
            this.#events.shift();
        }
        this.#events.push(event);
        return true;
    }

    drainForSession(sessionId: string, generation: number, handlers: BufferedPtyEventHandlers): void {
        if (this.#activeGeneration !== generation) return;
        for (const event of this.#events) {
            if (event.payload.sessionId === sessionId) {
                dispatchBufferedPtyEvent(event, handlers);
            }
        }
        this.clear();
    }
}

const dispatchBufferedPtyEvent = (event: BufferedPtyEvent, handlers: BufferedPtyEventHandlers): void => {
    switch (event.type) {
        case 'output':
            handlers.onOutput(event.payload);
            return;
        case 'exited':
            handlers.onExited(event.payload);
            return;
        case 'busy':
            handlers.onBusy(event.payload);
            return;
    }
};

export { PtyTerminalEventBuffer };
