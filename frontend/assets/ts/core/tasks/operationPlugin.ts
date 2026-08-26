/* SoAI - Shared tasks operation plugin [frontend/assets/ts/core/tasks/operationPlugin.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TaskOperationEntry, TaskOperationMeta } from '@core/tasks/protocols.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import { isString } from '@core/typeGuards.ts';

const resolveTaskOperationPluginNameFromMeta = (meta: TaskOperationMeta | null | undefined): string | null => {
    const candidates = [meta?.['plugin'], meta?.['pluginName'], meta?.['provider'], meta?.['sourcePlugin']];
    for (const candidate of candidates) {
        const value = toTrimmedStringOrNull(candidate);
        if (value) {
            return value;
        }
    }
    return null;
};

const deriveTaskOperationPluginNameFromUniversalId = (meta: TaskOperationMeta | null | undefined): string | null => {
    const universalId = meta?.['universalId'];
    if (!isString(universalId) || !universalId.includes(':')) {
        return null;
    }
    const pluginName = universalId.split(':')[0]?.trim();
    return pluginName || null;
};

const resolveTaskOperationPluginName = (operation: TaskOperationEntry): string | null => {
    const directPluginName = toTrimmedStringOrNull(operation.pluginName);
    if (directPluginName) {
        return directPluginName;
    }
    return resolveTaskOperationPluginNameFromMeta(operation.meta) || deriveTaskOperationPluginNameFromUniversalId(operation.meta);
};

export { deriveTaskOperationPluginNameFromUniversalId, resolveTaskOperationPluginName, resolveTaskOperationPluginNameFromMeta };
