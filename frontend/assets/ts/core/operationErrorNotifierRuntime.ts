/* SoAI - Shared frontend operation error notifier runtime [frontend/assets/ts/core/operationErrorNotifierRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { OperationErrorNotifier } from '@core/operationErrorNotifier.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';

const OPERATION_ERROR_NOTIFIER_SERVICE_ID = 'core.operationErrorNotifier';

const requireOperationErrorNotifier = (): OperationErrorNotifier => {
    const candidate = resolveKernelService(OPERATION_ERROR_NOTIFIER_SERVICE_ID);
    if (!(candidate instanceof OperationErrorNotifier)) {
        throw new Error(`${OPERATION_ERROR_NOTIFIER_SERVICE_ID} is not configured`);
    }
    return candidate;
};

export { requireOperationErrorNotifier };
