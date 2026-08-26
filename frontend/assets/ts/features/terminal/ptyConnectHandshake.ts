/* SoAI - Terminal feature PTY connect handshake [frontend/assets/ts/features/terminal/ptyConnectHandshake.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createDeferred, type Deferred } from '@core/runtime/deferred.ts';
import { i18n } from '@core/i18n/index.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { PTYTerminalConnectError } from '@features/terminal/PTYTerminalViewSupport.ts';

class PtyConnectHandshake {
    readonly #timers = new ResourceTracker();
    #deferred: Deferred<string> | null = null;
    #timeoutId: number | null = null;

    start(timeoutMs: number): Deferred<string> {
        if (this.#deferred) {
            throw new Error('PTY connect handshake already active');
        }
        const deferred = createDeferred<string>();
        this.#deferred = deferred;
        this.#timeoutId = this.#timers.setTimeout(() => {
            deferred.reject(new PTYTerminalConnectError(i18n.t('terminal.status.connectionTimedOut'), 'timeout_error'));
        }, timeoutMs);
        return deferred;
    }

    waitForPending(): Promise<string> | null {
        return this.#deferred ? this.#deferred.promise : null;
    }

    resolve(sessionId: string): void {
        this.#deferred?.resolve(sessionId);
    }

    reject(message: string, code: string | null): void {
        this.#deferred?.reject(new PTYTerminalConnectError(message, code));
    }

    clear(): void {
        if (this.#timeoutId) {
            this.#timers.clearTimer(this.#timeoutId);
            this.#timeoutId = null;
        }
        this.#deferred = null;
    }

    dispose(): void {
        if (this.#deferred) {
            this.#deferred.reject(new PTYTerminalConnectError(i18n.t('terminal.status.disposed'), 'disposed_error'));
        }
        this.clear();
        this.#timers.cleanup();
    }
}

export { PtyConnectHandshake };
