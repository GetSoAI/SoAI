/* SoAI - Rejection-neutral serialized preference operation queue [frontend/assets/ts/core/storage/chatpreferences/preferenceOperationQueue.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { StorageRuntimeState } from '@core/storage/service/types.ts';

const enqueuePreferenceOperation = <Result>(state: StorageRuntimeState, operation: () => Promise<Result>): Promise<Result> => {
    const task = state.writeQueue.then(operation);
    state.writeQueue = task.then(
        () => null,
        () => null
    );
    return task;
};

export { enqueuePreferenceOperation };
