/* SoAI - Shared models model status [frontend/assets/ts/core/models/modelStatus.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { PLUGIN_STATUS_BACKEND_INSTALLING, PLUGIN_STATUS_BACKEND_NOT_INSTALLED, PLUGIN_STATUS_BACKEND_UPDATING, PLUGIN_STATUS_DELETE_ERROR, PLUGIN_STATUS_DISABLED, PLUGIN_STATUS_INCOMPATIBLE, PLUGIN_STATUS_INSTALL_ERROR, PLUGIN_STATUS_LOAD_ERROR, PLUGIN_STATUS_PERSISTENT_READY, PLUGIN_STATUS_QUARANTINED, PLUGIN_STATUS_BACKEND_UNINSTALL_ERROR, PLUGIN_STATUS_UPDATE_ERROR } from '@core/state/pluginStatus.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';

const MODEL_STATUS_LOADING_VALUES: ReadonlySet<string> = new Set(['downloading', 'loading']);
const PLUGIN_STATUS_ERROR_VALUES: ReadonlySet<string> = new Set(['ERROR', PLUGIN_STATUS_INSTALL_ERROR, PLUGIN_STATUS_LOAD_ERROR, PLUGIN_STATUS_UPDATE_ERROR, PLUGIN_STATUS_BACKEND_UNINSTALL_ERROR, PLUGIN_STATUS_DELETE_ERROR, PLUGIN_STATUS_QUARANTINED]);
const PLUGIN_STATUS_LOADING_VALUES: ReadonlySet<string> = new Set([PLUGIN_STATUS_BACKEND_INSTALLING, PLUGIN_STATUS_BACKEND_UPDATING, 'STARTING', 'LOADING', 'REMOVING_BACKEND', 'DELETING']);
const PLUGIN_STATUS_READY_VALUES: ReadonlySet<string> = new Set(['READY_DIRTY', 'READY']);

type ModelStatusNormalizer = {
    normalizeStatus(status: JsonValue | undefined): string;
};

const resolveNormalizedPluginStatus = (statusManager: ModelStatusNormalizer | null, pluginStatus: JsonValue | undefined): string => {
    if (statusManager) {
        return String(statusManager.normalizeStatus(pluginStatus)).trim().toUpperCase();
    }
    return String(pluginStatus ?? '')
        .trim()
        .toUpperCase();
};

const resolveModelCatalogPhase = (statusManager: ModelStatusNormalizer | null, model: ModelRecord): string => {
    const isLoaded = model.isLoaded === true || model.loaded === true;
    if (model.type === 'virtual') {
        return PLUGIN_STATUS_PERSISTENT_READY;
    }

    const pluginStatus = resolveNormalizedPluginStatus(statusManager, model.pluginStatus);

    if (model.isEnabled === false) {
        return PLUGIN_STATUS_DISABLED;
    }
    if (pluginStatus === PLUGIN_STATUS_DISABLED) {
        return PLUGIN_STATUS_DISABLED;
    }

    const modelStatus = String(model.status ?? '').toLowerCase();
    if (MODEL_STATUS_LOADING_VALUES.has(modelStatus)) {
        return 'LOADING';
    }
    if (modelStatus === 'error' || model.isOrphaned === true) {
        return 'ERROR';
    }

    if (pluginStatus === PLUGIN_STATUS_INCOMPATIBLE) {
        return PLUGIN_STATUS_INCOMPATIBLE;
    }
    if (PLUGIN_STATUS_ERROR_VALUES.has(pluginStatus)) {
        return pluginStatus;
    }
    if (pluginStatus === 'STOPPING') {
        return 'STOPPING';
    }
    if (PLUGIN_STATUS_LOADING_VALUES.has(pluginStatus)) {
        return pluginStatus;
    }
    if (pluginStatus === PLUGIN_STATUS_BACKEND_NOT_INSTALLED) {
        return PLUGIN_STATUS_BACKEND_NOT_INSTALLED;
    }
    if (pluginStatus === 'NOT_DETECTED' || pluginStatus === 'ABSENT') {
        return pluginStatus;
    }
    if (pluginStatus === 'READY_PENDING_DISPATCH' && isLoaded) {
        return 'READY_PENDING_DISPATCH';
    }
    if (pluginStatus === 'PROCESSING' && isLoaded) {
        return 'PROCESSING';
    }
    if (PLUGIN_STATUS_READY_VALUES.has(pluginStatus) && isLoaded) {
        return pluginStatus;
    }
    if (pluginStatus === PLUGIN_STATUS_PERSISTENT_READY) {
        return PLUGIN_STATUS_PERSISTENT_READY;
    }
    return 'STOPPED';
};

const resolveModelStatus = (statusManager: ModelStatusNormalizer | null, model: ModelRecord): string => {
    const phase = resolveModelCatalogPhase(statusManager, model);
    if (PLUGIN_STATUS_ERROR_VALUES.has(phase)) {
        return 'ERROR';
    }
    if (PLUGIN_STATUS_LOADING_VALUES.has(phase)) {
        return 'LOADING';
    }
    return phase;
};

export { MODEL_STATUS_LOADING_VALUES, PLUGIN_STATUS_ERROR_VALUES, PLUGIN_STATUS_LOADING_VALUES, PLUGIN_STATUS_READY_VALUES, resolveModelCatalogPhase, resolveModelStatus };
export type { ModelStatusNormalizer };
