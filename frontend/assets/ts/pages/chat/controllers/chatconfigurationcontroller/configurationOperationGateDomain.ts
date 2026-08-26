/* SoAI - Chat configuration mutation admission gate [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/configurationOperationGateDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';

type ChatConfigurationOperation = 'save' | 'preset';

class ConfigurationOperationGate {
    #active: ChatConfigurationOperation | null = null;
    readonly #listeners = new Set<() => void>();

    canAcquire(): boolean {
        return this.#active === null;
    }

    activeOperation(): ChatConfigurationOperation | null {
        return this.#active;
    }

    acquire(operation: ChatConfigurationOperation): (() => void) | null {
        if (this.#active !== null) {
            return null;
        }
        this.#active = operation;
        this.#emit();
        let released = false;
        return (): void => {
            if (released) {
                return;
            }
            released = true;
            if (this.#active !== operation) {
                throw new Error('Chat configuration operation gate lease ownership changed.');
            }
            this.#active = null;
            this.#emit();
        };
    }

    subscribe(listener: () => void): () => void {
        this.#listeners.add(listener);
        return (): void => {
            this.#listeners.delete(listener);
        };
    }

    #emit(): void {
        for (const listener of this.#listeners) {
            try {
                listener();
            } catch (error) {
                errorHandler.warn('ChatConfigurationOperationGate', 'Operation-state subscriber failed', ensureError(error));
            }
        }
    }
}

export { ConfigurationOperationGate };
export type { ChatConfigurationOperation };
