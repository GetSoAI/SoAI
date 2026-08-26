/* SoAI - Shared frontend WebSocket client connection wait registry [frontend/assets/ts/core/websocketclient/connectionWaitRegistry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

class WebSocketConnectionWaitRegistry {
    #connectedListeners: Set<() => void> = new Set();
    #closedListeners: Set<(error: Error) => void> = new Set();

    subscribeConnected(listener: () => void): () => void {
        this.#connectedListeners.add(listener);
        return () => this.#connectedListeners.delete(listener);
    }

    subscribeClosed(listener: (error: Error) => void): () => void {
        this.#closedListeners.add(listener);
        return () => this.#closedListeners.delete(listener);
    }

    notifyConnected(): void {
        this.#connectedListeners.forEach((listener) => listener());
    }

    notifyClosed(reason: string): void {
        const closeError = new Error(`WebSocket connection closed: ${reason}`);
        this.#closedListeners.forEach((listener) => listener(closeError));
    }
}

export { WebSocketConnectionWaitRegistry };
