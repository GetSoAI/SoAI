/* SoAI - Authoritative chat preference invalidation convergence [frontend/assets/ts/core/storage/chatpreferences/ChatPreferenceInvalidationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CrossTabPublishOutcome } from '@core/crosstab/channel.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { StorageRuntimeState, TabStateManagerContract } from '@core/storage/service/types.ts';
import { isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';

const CHAT_PREFERENCES_CHANNEL_ID = 'soai.webui.chat-preferences';

class ChatPreferenceInvalidationController {
    readonly #state: Pick<StorageRuntimeState, 'isAuthenticated' | 'windowIdentity'>;
    readonly #channel: ReturnType<TabStateManagerContract['getCrossTabChannel']>;
    readonly #refresh: () => Promise<void>;
    #epoch = 0;
    #refreshRunning = false;
    #retryAttempt = 0;
    #retryHandle: ReturnType<typeof setTimeout> | null = null;
    #disposed = false;

    constructor(options: { state: Pick<StorageRuntimeState, 'isAuthenticated' | 'windowIdentity'>; stateManager: Pick<TabStateManagerContract, 'getCrossTabChannel'>; refresh: () => Promise<void> }) {
        this.#state = options.state;
        this.#channel = options.stateManager.getCrossTabChannel(CHAT_PREFERENCES_CHANNEL_ID);
        this.#refresh = options.refresh;
    }

    subscribe(): () => void {
        const unsubscribe = this.#channel.subscribe((message) => this.#handle(message));
        return (): void => {
            this.#disposed = true;
            unsubscribe();
            if (this.#retryHandle !== null) clearTimeout(this.#retryHandle);
            this.#retryHandle = null;
        };
    }

    publish(windowId: string): CrossTabPublishOutcome {
        return this.#channel.publish({ version: 1, type: 'chat-preferences-invalidated', 'origin_window_id': windowId });
    }

    #handle(message: JsonValue | null): void {
        if (
            !isJsonObject(message) ||
            Object.keys(message)
                .sort((left, right) => left.localeCompare(right, 'en'))
                .join(',') !== 'origin_window_id,type,version' ||
            message['version'] !== 1 ||
            message['type'] !== 'chat-preferences-invalidated' ||
            typeof message['origin_window_id'] !== 'string' ||
            message['origin_window_id'] === this.#state.windowIdentity
        )
            return;
        this.#epoch += 1;
        this.#retryAttempt = 0;
        this.#scheduleRefresh();
    }

    #scheduleRefresh(): void {
        if (this.#disposed || this.#refreshRunning || this.#retryHandle !== null || !this.#state.isAuthenticated) return;
        const epoch = this.#epoch;
        this.#refreshRunning = true;
        void this.#refresh()
            .then(() => {
                if (epoch === this.#epoch) this.#retryAttempt = 0;
            })
            .catch((error) => this.#handleRefreshFailure(error, epoch))
            .finally(() => {
                this.#refreshRunning = false;
                if (epoch !== this.#epoch) this.#scheduleRefresh();
            });
    }

    #handleRefreshFailure<Failure>(error: Failure, epoch: number): void {
        if (this.#disposed || epoch !== this.#epoch) return;
        if (this.#retryAttempt >= 3) {
            errorHandler.warn('StorageManager', 'Chat preference invalidation refresh failed after bounded recovery', ensureError(error));
            return;
        }
        const delayMs = 250 * 2 ** this.#retryAttempt;
        this.#retryAttempt += 1;
        this.#retryHandle = setTimeout(() => {
            this.#retryHandle = null;
            this.#scheduleRefresh();
        }, delayMs);
    }
}

export { ChatPreferenceInvalidationController };
