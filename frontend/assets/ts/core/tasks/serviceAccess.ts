/* SoAI - Shared tasks service access [frontend/assets/ts/core/tasks/serviceAccess.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { TASK_MANAGER_SERVICE_ID, type TaskOperationsApi } from '@core/tasks/protocols.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';
import { hasFunctionProperty, isObject } from '@core/typeGuards.ts';

const isTaskOperationsApi = <T>(value: T): value is T & TaskOperationsApi => {
    return isObject(value) && hasFunctionProperty(value, 'getOperations') && hasFunctionProperty(value, 'subscribeOperations') && hasFunctionProperty(value, 'reconcileOperations') && hasFunctionProperty(value, 'cancelOperationById') && hasFunctionProperty(value, 'getPluginKey') && hasFunctionProperty(value, 'upsertLocalOperation') && hasFunctionProperty(value, 'removeLocalOperation');
};

const requireTaskOperationsApi = (): TaskOperationsApi => {
    const service = resolveKernelService(TASK_MANAGER_SERVICE_ID);
    if (!isTaskOperationsApi(service)) {
        throw new Error(`${TASK_MANAGER_SERVICE_ID} must expose the task operations API`);
    }
    return service;
};

export { isTaskOperationsApi, requireTaskOperationsApi };
