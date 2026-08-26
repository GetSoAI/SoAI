/* SoAI - Shared frontend connection status initial snapshot [frontend/assets/ts/core/connectionstatus/initialSnapshot.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import type { StatusSnapshot } from '@core/connectionstatus/types.ts';

interface WaitForInitialSnapshotOptions {
    timeout: number;
    hasCurrentStatus: () => boolean;
    getSnapshot: () => StatusSnapshot | null;
    isAuthenticated: () => boolean;
    setTimer: (handler: () => void, delay: number) => number | null;
    clearTimer: (timerId: number | null) => void;
    addWaiter: (waiter: { resolve: () => void; reject: (error: Error) => void }) => void;
    ensureStream: () => Promise<void> | null;
}

const waitForInitialConnectionSnapshot = async (options: WaitForInitialSnapshotOptions): Promise<StatusSnapshot | null> => {
    if (options.hasCurrentStatus()) {
        return options.getSnapshot();
    }
    if (!options.isAuthenticated()) {
        return null;
    }
    return new Promise((resolve, reject) => {
        let completed = false;
        let timer: number | null = null;
        const finish = (callback: () => void): void => {
            if (completed) {
                return;
            }
            completed = true;
            if (timer !== null) {
                options.clearTimer(timer);
            }
            callback();
        };
        const waiter = {
            resolve: (): void => finish(() => resolve(options.getSnapshot())),
            reject: (error: Error): void => finish(() => reject(error))
        };
        if (options.timeout > 0) {
            timer = options.setTimer(() => waiter.reject(new Error('Timed out while waiting for system status')), options.timeout);
        }
        options.addWaiter(waiter);
        const task = options.ensureStream();
        if (!task) {
            waiter.reject(new Error('Stream manager unavailable'));
            return;
        }
        void task.catch((error) => waiter.reject(ensureError(error)));
    });
};

export { waitForInitialConnectionSnapshot };
