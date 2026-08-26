/* SoAI - Shared realtime accepted task operation [frontend/assets/ts/core/realtime/streammanager/actions/acceptedTaskOperation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import type { OperationMetadata } from '@core/realtime/streammanager/types.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

interface TaskOperationEmitter {
    (id: string, type: string, status: string, meta: OperationMetadata, data: JsonObject): void;
}

const emitAcceptedTaskOperation = (options: { taskId: string; operationMeta: OperationMetadata; previousMeta: OperationMetadata | null; emitOperation: TaskOperationEmitter }): void => {
    const operationType = toTrimmedString(options.operationMeta.type) || 'unknown';
    if (operationType === 'unknown') {
        return;
    }
    options.emitOperation(options.taskId, operationType, options.previousMeta ? 'progress' : 'start', options.operationMeta, {});
};

export { emitAcceptedTaskOperation };
export type { TaskOperationEmitter };
