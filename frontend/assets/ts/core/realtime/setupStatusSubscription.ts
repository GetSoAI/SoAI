/* SoAI - Restricted setup status subscription lifecycle [frontend/assets/ts/core/realtime/setupStatusSubscription.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { decodeSetupStatusEvent, type SetupStatusSnapshot } from '@core/realtime/eventcontracts/setupStatusContracts.ts';
import { parseRequiredJsonText } from '@core/serialization/json.ts';
import { WebSocketConnectionController } from '@core/websocketclient/WebSocketConnectionController.ts';

class SetupStatusSubscription {
    readonly #connection: WebSocketConnectionController;
    #destroyed = false;

    constructor(onSnapshot: (snapshot: SetupStatusSnapshot) => void) {
        this.#connection = new WebSocketConnectionController(
            {
                onConnected: () => {},
                onDisconnectedEvent: () => {},
                onClosed: () => {},
                onMessage: (event) => {
                    if (this.#destroyed) return;
                    try {
                        const snapshot = decodeSetupStatusEvent(parseRequiredJsonText(String(event.data)));
                        if (!snapshot.setupNeeded) this.destroy();
                        onSnapshot(snapshot);
                    } catch (error) {
                        errorHandler.warn('SetupStatusSubscription', 'Invalid restricted setup status event', ensureError(error));
                        this.#connection.closeWithReason('setup-status-invalid', undefined, true);
                        this.#connection.scheduleReconnect();
                    }
                }
            },
            'setup-status'
        );
    }

    connect(): void {
        if (!this.#destroyed) this.#connection.connect();
    }

    readonly destroy = (): void => {
        this.#destroyed = true;
        this.#connection.destroy();
    };
}

export { SetupStatusSubscription };
