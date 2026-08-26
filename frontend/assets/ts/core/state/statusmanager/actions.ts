/* SoAI - Shared state status manager actions [frontend/assets/ts/core/state/statusmanager/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { COLLECTION_BADGE_CLASS_MAP, COLLECTION_STATUS_CLASS_MAP, DEFAULT_STATUS_CONFIG, type StatusColor, type StatusDefinition } from '@core/state/constants.ts';
import { i18n } from '@core/i18n/index.ts';
import { deriveAllowedColors, deriveDefinitions, deriveStatusSet, normalizeStatusKey } from '@core/state/statusNormalization.ts';
import type { StatusInput, StatusKey } from '@core/state/statusTypes.ts';
import type { BackendPayload, StreamManager } from '@core/state/statusmanager/contracts.ts';
import { hasFunctionProperty, isObject } from '@core/typeGuards.ts';
import type { StatusManagerState } from '@core/state/statusmanager/internalContracts.ts';
import { createInitialState, resetState } from '@core/state/statusmanager/state.ts';
import { readStatusFromPayload } from '@core/state/statusmanager/mappers.ts';

const SUPPORTED_STATUS_DEFINITION_PAYLOAD_KEYS = new Set(['states', 'default', 'allowedColors', 'tags']);

const requireDefinition = (state: StatusManagerState, status: StatusKey): StatusDefinition => {
    const definition = state.definitions[status];
    if (definition) {
        return definition;
    }
    const fallback = state.definitions[state.defaultStatus];
    if (fallback) {
        return fallback;
    }
    throw new Error(`StatusManager definitions are missing required default status "${state.defaultStatus}"`);
};

const initializeState = (): StatusManagerState => {
    return createInitialState();
};

const resetStatusState = (state: StatusManagerState): void => {
    resetState(state);
};

const getRawDefinition = (state: StatusManagerState, status: StatusKey): StatusDefinition => {
    return requireDefinition(state, status);
};

const normalizeStatus = (state: StatusManagerState, status: StatusInput): StatusKey => {
    const normalized = normalizeStatusKey(status);
    return normalized && state.definitions[normalized] ? normalized : state.defaultStatus;
};

const resolveStatusDefinition = (state: StatusManagerState, status: StatusInput): StatusDefinition => {
    return getRawDefinition(state, normalizeStatus(state, status));
};

const resolveStatusColor = (state: StatusManagerState, status: StatusInput): StatusColor => {
    const definition = resolveStatusDefinition(state, status);
    const color = definition.color;
    if (state.allowedColors.includes(color)) {
        return color;
    }
    return requireDefinition(state, state.defaultStatus).color;
};

const resolveStatusDefinitionText = (status: StatusKey, definition: StatusDefinition): string => {
    switch (status) {
        case 'UNKNOWN':
            return i18n.t('statusCatalog.default.unknown');
        case 'STOPPED':
            return i18n.t('statusCatalog.default.stopped');
        case 'STARTING':
            return i18n.t('statusCatalog.default.starting');
        case 'LOADING':
            return i18n.t('statusCatalog.default.loading');
        case 'IDLE':
            return i18n.t('statusCatalog.default.idle');
        case 'READY_PENDING_DISPATCH':
            return i18n.t('statusCatalog.default.readyPendingDispatch');
        case 'READY':
            return i18n.t('statusCatalog.default.ready');
        case 'READY_DIRTY':
            return i18n.t('statusCatalog.default.readyDirty');
        case 'PROCESSING':
            return i18n.t('statusCatalog.default.processing');
        case 'STOPPING':
            return i18n.t('statusCatalog.default.stopping');
        case 'ERROR':
            return i18n.t('statusCatalog.default.error');
        case 'QUARANTINED':
            return i18n.t('statusCatalog.default.quarantined');
        case 'DISABLED':
            return i18n.t('statusCatalog.default.disabled');
        case 'INCOMPATIBLE':
            return i18n.t('statusCatalog.default.incompatible');
        case 'NOT_DETECTED':
            return i18n.t('statusCatalog.default.notDetected');
        case 'BACKEND_NOT_INSTALLED':
            return i18n.t('statusCatalog.default.backendNotInstalled');
        case 'BACKEND_INSTALLING':
            return i18n.t('statusCatalog.default.backendInstalling');
        case 'BACKEND_UPDATING':
            return i18n.t('statusCatalog.default.backendUpdating');
        case 'REMOVING_BACKEND':
            return i18n.t('statusCatalog.default.removing');
        case 'DELETING':
            return i18n.t('statusCatalog.default.deleting');
        case 'INSTALL_ERROR':
            return i18n.t('statusCatalog.default.installError');
        case 'LOAD_ERROR':
            return i18n.t('statusCatalog.default.loadError');
        case 'UPDATE_ERROR':
            return i18n.t('statusCatalog.default.updateError');
        case 'BACKEND_UNINSTALL_ERROR':
            return i18n.t('statusCatalog.default.backendUninstallError');
        case 'DELETE_ERROR':
            return i18n.t('statusCatalog.default.deleteError');
        case 'PERSISTENT_READY':
            return i18n.t('statusCatalog.default.persistentReady');
        case 'ABSENT':
            return i18n.t('statusCatalog.default.absent');
    }
    if (definition.description) {
        return definition.description;
    }
    throw new Error(`Status "${status}" is missing a localized or explicit description`);
};

const resolveStatusDescription = (state: StatusManagerState, status: StatusInput): string => {
    const normalized = normalizeStatus(state, status);
    return resolveStatusDefinitionText(normalized, getRawDefinition(state, normalized));
};

const resolveCollectionStatusClass = (state: StatusManagerState, status: StatusInput): string => {
    return COLLECTION_STATUS_CLASS_MAP[resolveStatusColor(state, status)] || 'status-neutral';
};

const resolveCollectionBadgeClass = (state: StatusManagerState, status: StatusInput): string => {
    return COLLECTION_BADGE_CLASS_MAP[resolveStatusColor(state, status)] || 'status-grey';
};

const isActive = (state: StatusManagerState, status: StatusInput): boolean => {
    return state.activeStatuses.has(normalizeStatus(state, status));
};

const isError = (state: StatusManagerState, status: StatusInput): boolean => {
    return state.errorStatuses.has(normalizeStatus(state, status));
};

const isTransitioning = (state: StatusManagerState, status: StatusInput): boolean => {
    return state.transitionStatuses.has(normalizeStatus(state, status));
};

const canUseStreamManager = <T>(value: T): value is T & StreamManager => {
    return isObject(value) && hasFunctionProperty(value, 'getResource') && hasFunctionProperty(value, 'subscribeResourceState');
};

const listStatuses = (state: StatusManagerState): StatusKey[] => {
    return Object.keys(state.definitions);
};

const listColors = (state: StatusManagerState): string[] => {
    return state.allowedColors.slice();
};

const applyBackendPayload = (state: StatusManagerState, payload: BackendPayload): void => {
    for (const key of Object.keys(payload)) {
        if (!SUPPORTED_STATUS_DEFINITION_PAYLOAD_KEYS.has(key)) {
            throw new Error('Unsupported status definition payload key set.');
        }
    }
    const definitions = deriveDefinitions(payload.states);
    if (!definitions || !Object.keys(definitions).length) {
        return;
    }
    state.definitions = definitions;
    const candidateDefault = normalizeStatusKey(payload.default);
    state.defaultStatus = candidateDefault && state.definitions[candidateDefault] ? candidateDefault : state.definitions['UNKNOWN'] ? 'UNKNOWN' : DEFAULT_STATUS_CONFIG.defaultStatus;
    state.allowedColors = deriveAllowedColors(payload.allowedColors, state.definitions);
    const tags = payload && isObject(payload.tags) ? payload.tags : {};
    state.activeStatuses = new Set(deriveStatusSet(tags.active, state.definitions));
    state.errorStatuses = new Set(deriveStatusSet(tags.error, state.definitions));
    state.transitionStatuses = new Set(deriveStatusSet(tags.transition, state.definitions));
};

const buildStatusSnapshot = (state: StatusManagerState, value: StatusInput): StatusInput => {
    const safeValue = readStatusFromPayload(value);
    return normalizeStatus(state, safeValue);
};

export { applyBackendPayload, canUseStreamManager, buildStatusSnapshot, initializeState, isActive, isError, isTransitioning, listColors, listStatuses, normalizeStatus, resolveCollectionBadgeClass, resolveCollectionStatusClass, resolveStatusColor, resolveStatusDefinition, resolveStatusDefinitionText, resolveStatusDescription, resetStatusState, getRawDefinition };
