/* SoAI - Tasks feature task manager store validation [frontend/assets/ts/features/tasks/taskmanagerstore/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasFunctionProperty, isObject } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { OperationReconciliationHost, OperationSubscriptionHost, PluginResourceSubscriptionHost } from '@features/tasks/taskmanagerstore/contracts.ts';
import type { TaskManagerStreamManager } from '@features/tasks/taskmanager/taskManagerTypes.ts';

const toUpperCaseValue = (value: string | null | undefined): string => String(value || '').toUpperCase();

type TaskManagerStoreGuardCandidate = JsonValue | OperationReconciliationHost | OperationSubscriptionHost | PluginResourceSubscriptionHost | TaskManagerStreamManager | null;

const isOperationSubscriptionHost = (value: TaskManagerStoreGuardCandidate): value is OperationSubscriptionHost => {
    if (!isObject(value)) return false;
    return hasFunctionProperty(value, 'subscribeOperations') && hasFunctionProperty(value, 'subscribeTerminalTasks');
};

const isOperationReconciliationHost = (value: TaskManagerStoreGuardCandidate): value is OperationReconciliationHost => {
    if (!isObject(value)) return false;
    return hasFunctionProperty(value, 'reconnectOperations');
};

const isPluginResourceSubscriptionHost = (value: TaskManagerStoreGuardCandidate): value is PluginResourceSubscriptionHost => {
    if (!isObject(value)) return false;
    return hasFunctionProperty(value, 'subscribeResourceState') && hasFunctionProperty(value, 'ensureResourceStarted');
};

export { isOperationReconciliationHost, isOperationSubscriptionHost, isPluginResourceSubscriptionHost, toUpperCaseValue };
