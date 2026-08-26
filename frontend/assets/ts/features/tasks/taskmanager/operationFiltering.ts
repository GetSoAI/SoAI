/* SoAI - Tasks feature operation filtering [frontend/assets/ts/features/tasks/taskmanager/operationFiltering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedLower, toTrimmedString } from '@core/normalize.ts';
import { resolveTaskOperationConversationId } from '@core/tasks/operationPayloads.ts';
import type { TaskOperationEntry, TaskOperationFilter } from '@core/tasks/protocols.ts';

const normalizeString = (value: string | null | undefined): string => {
    return toTrimmedLower(value);
};

const filterTaskOperations = (operations: readonly TaskOperationEntry[], filter: TaskOperationFilter | null | undefined, getPluginKey: (source: string | null | undefined) => string | null): TaskOperationEntry[] => {
    const types = filter?.types ? new Set(filter.types) : null;
    const pluginKey = normalizeString(filter?.pluginKey) || normalizeString(getPluginKey(filter?.pluginName ?? null));
    const conversationId = toTrimmedString(filter?.conversationId);
    const result: TaskOperationEntry[] = [];

    for (const operation of operations) {
        if (types && !types.has(operation.type)) {
            continue;
        }
        if (pluginKey && normalizeString(operation.pluginKey) !== pluginKey) {
            continue;
        }
        if (conversationId && resolveTaskOperationConversationId(operation.meta) !== conversationId) {
            continue;
        }
        result.push(operation);
    }
    return result;
};

export { filterTaskOperations };
