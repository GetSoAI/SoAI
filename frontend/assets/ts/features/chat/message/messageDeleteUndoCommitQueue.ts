/* SoAI - Chat feature message delete undo commit queue [frontend/assets/ts/features/chat/message/messageDeleteUndoCommitQueue.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';

type KeyedCommitQueueOptions = {
    isKeyActive: (key: string) => boolean;
    onKeyIdle: (key: string) => void;
};

class ChatMessageDeleteUndoCommitQueue {
    readonly #tailByKey: Map<string, Promise<void>>;

    constructor() {
        this.#tailByKey = new Map();
    }

    dispose(): void {
        this.#tailByKey.clear();
    }

    enqueue(key: string, task: () => Promise<void>, options: KeyedCommitQueueOptions): Promise<void> {
        const previousTail = this.#tailByKey.get(key) ?? Promise.resolve();
        const nextTail = (async (): Promise<void> => {
            try {
                await previousTail;
            } catch (error) {
                errorHandler.warn('ChatMessageDeleteUndoCommitQueue', 'Previous commit task failed', ensureError(error));
            }
            await task();
        })();
        const trackedTail = nextTail.catch((error) => {
            errorHandler.warn('ChatMessageDeleteUndoCommitQueue', 'Commit task failed', ensureError(error));
        });

        this.#tailByKey.set(key, trackedTail);

        terminateHandledPromise(
            trackedTail.finally(() => {
                if (this.#tailByKey.get(key) !== trackedTail) {
                    return;
                }
                if (options.isKeyActive(key)) {
                    return;
                }
                this.#tailByKey.delete(key);
                options.onKeyIdle(key);
            })
        );

        return nextTail;
    }

    async waitForIdle(key: string): Promise<void> {
        while (true) {
            const tail = this.#tailByKey.get(key);
            if (tail === undefined) {
                return;
            }
            await tail;
            if (this.#tailByKey.get(key) === tail) {
                return;
            }
        }
    }
}

export { ChatMessageDeleteUndoCommitQueue };
