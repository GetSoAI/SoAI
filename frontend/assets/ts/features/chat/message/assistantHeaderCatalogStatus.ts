/* SoAI - Chat feature assistant header catalog status [frontend/assets/ts/features/chat/message/assistantHeaderCatalogStatus.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveModelCatalogPhase, type ModelStatusNormalizer } from '@core/models/modelStatus.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';

type AssistantHeaderActivityStatus = 'pending' | 'running' | 'completed' | 'cancelled' | 'error';

const ASSISTANT_HEADER_ACTIVITY_STATUS_CLASSES: ReadonlyArray<string> = Object.freeze(['inline-activity-status-pending', 'inline-activity-status-running', 'inline-activity-status-completed', 'inline-activity-status-cancelled', 'inline-activity-status-error']);
const ASSISTANT_RESPONSE_STATUS_ATTRIBUTE = 'data-assistant-response-status';

const PENDING_MODEL_CATALOG_PHASES: ReadonlySet<string> = new Set(['STARTING', 'LOADING', 'READY_PENDING_DISPATCH', 'STOPPING', 'BACKEND_INSTALLING', 'BACKEND_UPDATING', 'REMOVING_BACKEND', 'DELETING']);
const READY_MODEL_CATALOG_PHASES: ReadonlySet<string> = new Set(['READY', 'READY_DIRTY', 'PERSISTENT_READY']);
const ERROR_MODEL_CATALOG_PHASES: ReadonlySet<string> = new Set(['ERROR', 'INCOMPATIBLE', 'BACKEND_NOT_INSTALLED', 'INSTALL_ERROR', 'LOAD_ERROR', 'UPDATE_ERROR', 'BACKEND_UNINSTALL_ERROR', 'DELETE_ERROR', 'QUARANTINED']);

const resolveAssistantHeaderActivityStatusFromPhase = (phase: string): AssistantHeaderActivityStatus | null => {
    if (phase === 'PROCESSING') {
        return 'running';
    }
    if (PENDING_MODEL_CATALOG_PHASES.has(phase)) {
        return 'pending';
    }
    if (READY_MODEL_CATALOG_PHASES.has(phase)) {
        return 'completed';
    }
    if (ERROR_MODEL_CATALOG_PHASES.has(phase)) {
        return 'error';
    }
    return null;
};

const resolveAssistantHeaderActivityStatus = (statusManager: ModelStatusNormalizer, model: ModelRecord): AssistantHeaderActivityStatus | null => {
    return resolveAssistantHeaderActivityStatusFromPhase(resolveModelCatalogPhase(statusManager, model));
};

const resolveAssistantHeaderActivityStatusClass = (status: AssistantHeaderActivityStatus | null): string | null => {
    return status === null ? null : `inline-activity-status-${status}`;
};

const assistantHeaderActivityHasResponseLifecycleStatus = (activity: HTMLElement): boolean => {
    return resolveAssistantHeaderResponseLifecycleStatusClass(activity) !== null;
};

const resolveAssistantHeaderResponseLifecycleStatusClass = (activity: HTMLElement): string | null => {
    const responseStatus = activity.getAttribute(ASSISTANT_RESPONSE_STATUS_ATTRIBUTE);
    if (responseStatus === 'running') {
        return 'inline-activity-status-running';
    }
    if (responseStatus === 'completed') {
        return 'inline-activity-status-completed';
    }
    return null;
};

const syncAssistantHeaderActivityStatusClass = (activity: HTMLElement, statusClass: string | null): boolean => {
    let changed = false;
    for (const className of ASSISTANT_HEADER_ACTIVITY_STATUS_CLASSES) {
        const enabled = className === statusClass;
        if (activity.classList.contains(className) === enabled) {
            continue;
        }
        activity.classList.toggle(className, enabled);
        changed = true;
    }
    return changed;
};

const syncAssistantHeaderActivityCatalogStatus = (inputArguments: { activity: HTMLElement; model: ModelRecord; statusManager: ModelStatusNormalizer }): void => {
    const phase = resolveModelCatalogPhase(inputArguments.statusManager, inputArguments.model);
    const status = resolveAssistantHeaderActivityStatusFromPhase(phase);
    inputArguments.activity.dataset['modelCatalogPhase'] = phase;
    const lifecycleStatusClass = resolveAssistantHeaderResponseLifecycleStatusClass(inputArguments.activity);
    if (lifecycleStatusClass !== null) {
        syncAssistantHeaderActivityStatusClass(inputArguments.activity, lifecycleStatusClass);
        return;
    }
    syncAssistantHeaderActivityStatusClass(inputArguments.activity, resolveAssistantHeaderActivityStatusClass(status));
};

const clearAssistantHeaderActivityCatalogStatus = (activity: HTMLElement): void => {
    activity.dataset['modelCatalogPhase'] = 'UNKNOWN';
    const lifecycleStatusClass = resolveAssistantHeaderResponseLifecycleStatusClass(activity);
    if (lifecycleStatusClass !== null) {
        syncAssistantHeaderActivityStatusClass(activity, lifecycleStatusClass);
        return;
    }
    syncAssistantHeaderActivityStatusClass(activity, null);
};

export { ASSISTANT_HEADER_ACTIVITY_STATUS_CLASSES, ASSISTANT_RESPONSE_STATUS_ATTRIBUTE, assistantHeaderActivityHasResponseLifecycleStatus, clearAssistantHeaderActivityCatalogStatus, resolveAssistantHeaderActivityStatus, syncAssistantHeaderActivityCatalogStatus, syncAssistantHeaderActivityStatusClass };
export type { AssistantHeaderActivityStatus };
