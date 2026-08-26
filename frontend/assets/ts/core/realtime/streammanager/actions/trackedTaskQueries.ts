/* SoAI - Accepted task operation index queries [frontend/assets/ts/core/realtime/streammanager/actions/trackedTaskQueries.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import type { OperationMetadata } from '@core/realtime/streammanager/types.ts';

const hasActiveTrackedOperationType = (trackedTasks: ReadonlyMap<string, OperationMetadata>, types: string | readonly string[]): boolean => {
    const typeSet = new Set(Array.isArray(types) ? types : [types]);
    for (const metadata of trackedTasks.values()) {
        const operationType = toTrimmedString(metadata.type);
        if (operationType && typeSet.has(operationType)) return true;
    }
    return false;
};

export { hasActiveTrackedOperationType };
