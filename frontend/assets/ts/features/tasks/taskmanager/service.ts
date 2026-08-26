/* SoAI - Tasks feature task manager service [frontend/assets/ts/features/tasks/taskmanager/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveTaskOperationDetailText, resolveTaskOperationLabelText, resolveTaskOperationMeta } from '@core/tasks/operationText.ts';
import { securityApi } from '@core/security/public.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { readRequiredTrimmedStringMessageValue } from '@core/types/payloadValueReaders.ts';
import { resolveProgressUsageClass } from '@core/ui/progressWidths.ts';
import type { OperationEntry, OperationMeta } from '@features/tasks/taskmanager/taskManagerModels.ts';
import type { TaskManagerStoreApi } from '@features/tasks/taskmanager/taskManagerTypes.ts';

interface OperationContext {
    name: string;
    meta: OperationMeta;
}

interface OperationLabelDependencies {
    store: TaskManagerStoreApi;
}

const resolveOperationContext = (op: OperationEntry): OperationContext => {
    const meta = resolveTaskOperationMeta(op);
    const pluginName = toTrimmedString(op.pluginName);
    const displayName = toTrimmedString(meta['displayName']);
    const metaPlugin = toTrimmedString(meta['plugin']);
    const resolved = pluginName || displayName || metaPlugin;
    if (!resolved) {
        throw new Error('TaskManager operation is missing plugin identification');
    }
    return { name: resolved, meta };
};

const buildOperationSignature = (op: OperationEntry): string => {
    const id = readRequiredTrimmedStringMessageValue(op.id, 'TaskManager operation signature requires an identifier');
    const type = toTrimmedString(op.type);
    const cancelable = op.cancelable === true ? '1' : '0';
    return `${id}:${type}:${cancelable}`;
};

const renderOperationRow = (op: OperationEntry, dependencies: OperationLabelDependencies): string => {
    const progress = dependencies.store.normalizeProgress(op.progress);
    const id = readRequiredTrimmedStringMessageValue(op.id, 'TaskManager operation requires an identifier to render');
    const escapedId = securityApi.escapeHtml(id);
    const label = resolveTaskOperationLabelText(op);
    const detail = resolveTaskOperationDetailText(op);

    return `<div class="task-operation-row task-operation-row--inline" data-operation="${escapedId}">
        <div class="task-operation-label">${securityApi.escapeHtml(label)}</div>
        <div class="task-operation-detail">${securityApi.escapeHtml(detail)}</div>
        <div class="task-progress task-progress--operation" role="progressbar" aria-valuenow="${progress}" aria-valuemin="0" aria-valuemax="100">
        <span class="task-progress-bar task-progress-bar--determinate ${resolveProgressUsageClass(progress)}" data-progress="${progress}"></span>
        </div>
        </div>`;
};

const resolveTaskStopButton = (target: EventTarget | null): HTMLElement | null => {
    if (!(target instanceof Element)) {
        return null;
    }
    const stopButton = target.closest('.task-stop-btn');
    return stopButton instanceof HTMLElement ? stopButton : null;
};

export { buildOperationSignature, renderOperationRow, resolveOperationContext, resolveTaskStopButton };
