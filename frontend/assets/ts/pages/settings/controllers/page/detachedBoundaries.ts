/* SoAI - Settings page detached boundaries [frontend/assets/ts/pages/settings/controllers/page/detachedBoundaries.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';

type BoundaryHost = {
    runWithBoundary: <T>(name: string, task: () => Promise<T> | T) => Promise<T>;
};

const runDetachedWithBoundary = <T>(host: BoundaryHost, boundaryName: string, task: () => Promise<T> | T): void => {
    void host.runWithBoundary(boundaryName, task).catch((error) => {
        errorHandler.warn('Settings', 'Detached boundary task failed', error);
    });
};

export { runDetachedWithBoundary };
export type { BoundaryHost };
