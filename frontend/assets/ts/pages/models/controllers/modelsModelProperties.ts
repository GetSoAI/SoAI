/* SoAI - Models page model properties [frontend/assets/ts/pages/models/controllers/modelsModelProperties.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveAssetPath } from '@core/assetPaths.ts';
import { i18n } from '@core/i18n/index.ts';
import { canDeleteModelRecord, isProviderBackedModelRecord } from '@core/models/modelDeletionEligibility.ts';
import { extractCleanModelId, resolveModelDisplayName, resolveModelItemCardId, resolveModelOriginId, resolveModelPluginName, resolveModelProviderName } from '@core/models/modelIdentity.ts';
import { resolveModelStatus } from '@core/models/modelStatus.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { capitalize } from '@core/primitives/text.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isObject, isString } from '@core/typeGuards.ts';
import type { ResourceIncomingObject, ResourceIncomingValue } from '@core/data/ClientDataHub.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { PROVIDER_MODE, resolveProviderMode } from '@features/catalog/public.ts';
import { BUILTIN_LOGO_FILES, PROVIDER_LOGO_PATHS, THIRD_PARTY_MODEL_LOGOS, VIRTUAL_MODEL_LOGO } from '@pages/models/contracts/ModelPageSupport.ts';

interface ModelsModelPropertiesDependencies {
    getIconSync: (iconName: IconName, options?: IconOptions) => TrustedHtml;
    getPluginByName: (name: string) => PluginRecord | null;
    isProviderPluginOperational: (plugin: PluginRecord) => boolean;
}

type ModelPropertyInput = ResourceIncomingValue | ModelRecord | null | undefined;

interface ModelEnabledToggleTarget {
    cardId: string;
    requestId: string;
    targetKey: string;
    targetType: 'model' | 'virtual';
}

const isModelObjectInput = (value: ModelPropertyInput): value is ModelRecord | ResourceIncomingObject => {
    if (!isObject(value)) return false;
    return true;
};

const isModelRecord = (value: ModelPropertyInput): value is ModelRecord => {
    if (!isModelObjectInput(value)) return false;
    const id = value['id'];
    const name = value['name'];
    const universalId = value['universalId'];
    return isString(id) || isString(name) || isString(universalId);
};

const getModelPlugin = (model: ModelPropertyInput): string => (isModelRecord(model) ? resolveModelPluginName(model) : '');

const getModelProvider = (model: ModelPropertyInput): string => (isModelRecord(model) ? resolveModelProviderName(model) : '');

const resolveModelsItemCardId = (model: ModelPropertyInput): string => (isModelRecord(model) ? resolveModelItemCardId(model) : '');

const resolveModelEnabledToggleTarget = (model: ModelPropertyInput): ModelEnabledToggleTarget | null => {
    if (!isModelRecord(model)) {
        return null;
    }
    const cardId = resolveModelsItemCardId(model);
    if (!cardId) {
        return null;
    }
    if (model.type === 'virtual') {
        const requestId = toTrimmedString(model.name) || toTrimmedString(model.id);
        if (!requestId) {
            return null;
        }
        return {
            cardId,
            requestId,
            targetKey: `virtual:${requestId}`,
            targetType: 'virtual'
        };
    }
    const requestId = toTrimmedString(model.universalId);
    if (!requestId) {
        return null;
    }
    return {
        cardId,
        requestId,
        targetKey: `model:${requestId}`,
        targetType: 'model'
    };
};

const getModelOriginId = (model: ModelPropertyInput): string => (isModelRecord(model) ? resolveModelOriginId(model) : '');

const getModelDisplayName = (model: ModelPropertyInput): string => (isModelRecord(model) ? resolveModelDisplayName(model) : '');

const extractCleanModelRuntimeId = (id: string): string => extractCleanModelId(id);

const formatStrategyLabel = (strategy: JsonValue | null | undefined): string => {
    if (!strategy) return '';
    const norm = String(strategy).trim().toLowerCase();
    switch (norm) {
        case 'load_balancing':
            return i18n.t('models.strategies.load_balancing');
        case 'failover':
            return i18n.t('models.strategies.failover');
        default:
            return i18n.t('common.unknown');
    }
};

const getModelStatus = (statusManager: { normalizeStatus(status: JsonValue | null | undefined): string }, model: ModelPropertyInput): string => {
    return isModelRecord(model) ? resolveModelStatus(statusManager, model) : 'STOPPED';
};

const getModelIcon = (dependencies: ModelsModelPropertiesDependencies, model: ModelPropertyInput, provider: JsonValue | null | undefined): TrustedHtml => {
    if (isModelObjectInput(model) && model['type'] === 'virtual') {
        return uiHtml`<img src="${uiAttr(resolveAssetPath(VIRTUAL_MODEL_LOGO))}" alt="${uiAttr(i18n.t('models.types.virtual'))}" class="provider-logo" />`;
    }
    const providerStr = String(provider ?? '');
    const provLower = providerStr.toLowerCase();
    const mapped = PROVIDER_LOGO_PATHS[provLower];
    if (mapped) {
        return uiHtml`<img src="${uiAttr(resolveAssetPath(mapped))}" alt="${uiAttr(providerStr)}" class="provider-logo" />`;
    }
    const plugin = dependencies.getPluginByName(providerStr);
    if (plugin) {
        const displayNameCandidate = plugin.displayName;
        const alt = isString(displayNameCandidate) ? displayNameCandidate : providerStr;
        let logoPath: string | undefined;
        if (plugin.isBuiltin === true) {
            const fileName = BUILTIN_LOGO_FILES[provLower];
            if (fileName) logoPath = resolveAssetPath(`img/logo/${fileName}`);
        } else {
            const mode = resolveProviderMode(plugin);
            const key = mode === PROVIDER_MODE.USER_MANAGED ? 'external' : 'default';
            logoPath = resolveAssetPath(THIRD_PARTY_MODEL_LOGOS[key]);
        }
        if (logoPath) return uiHtml`<img src="${uiAttr(logoPath)}" alt="${uiAttr(alt)}" class="provider-logo" />`;
    }
    return dependencies.getIconSync('model-default', { size: 20, strokeWidth: 1.5 });
};

const resolveGroupHeading = (inputArguments: { model: ModelRecord; sortKey: string; getModelPlugin: (model: ModelPropertyInput) => string; getModelProvider: (model: ModelPropertyInput) => string; getModelStatus: (model: ModelPropertyInput) => string; getModelDisplayName: (model: ModelPropertyInput) => string; getNameGroupKey: (name: string | null | undefined) => string | null; getPluginByName: (name: string) => PluginRecord | null; statusManager: { getDescription(status: string): string } }): { key: string | number | null; heading: string | null } => {
    const { model, sortKey } = inputArguments;
    if (sortKey === 'plugin') {
        const pluginName = inputArguments.getModelPlugin(model);
        if (!pluginName) return { key: null, heading: null };
        const plugin = inputArguments.getPluginByName(pluginName);
        const displayNameRaw = plugin?.displayName;
        const displayName = typeof displayNameRaw === 'string' ? displayNameRaw : capitalize(pluginName) || pluginName;
        return { key: pluginName, heading: displayName };
    }

    if (sortKey === 'provider') {
        const providerName = inputArguments.getModelProvider(model);
        const normalized = isString(providerName) ? providerName.trim() : '';
        const base = normalized || i18n.t('common.unknown');
        const label = capitalize(base) || base;
        const key = normalized ? normalized.toLowerCase() : 'unknown';
        return { key, heading: label };
    }

    if (sortKey === 'type') {
        const typeValue = model['type'];
        const type = isString(typeValue) ? typeValue : '';
        if (!type) return { key: null, heading: null };
        if (type === 'local') {
            return { key: type, heading: i18n.t('models.types.local') };
        }
        if (type === 'cloud') {
            return { key: type, heading: i18n.t('models.types.cloud') };
        }
        if (type === 'virtual') {
            return { key: type, heading: i18n.t('models.types.virtual') };
        }
        const label = capitalize(type) || i18n.t('models.types.unknown');
        return { key: type, heading: label };
    }

    if (sortKey === 'status') {
        const status = inputArguments.getModelStatus(model);
        if (!status) return { key: null, heading: null };
        const label = inputArguments.statusManager.getDescription(status);
        return { key: status, heading: String(label) };
    }

    if (sortKey === 'size') {
        const bytesValue = model.sizeBytes;
        const bytes = typeof bytesValue === 'number' ? bytesValue : 0;
        const gibibyte = 1024 ** 3;
        if (bytes <= 0) return { key: 'unknown', heading: i18n.t('models.sort.sizeGroups.unknown') };
        if (bytes < gibibyte) return { key: 'under-1', heading: i18n.t('models.sort.sizeGroups.under1') };
        if (bytes < 4 * gibibyte) return { key: '1-4', heading: i18n.t('models.sort.sizeGroups.from1To4') };
        if (bytes < 8 * gibibyte) return { key: '4-8', heading: i18n.t('models.sort.sizeGroups.from4To8') };
        if (bytes < 16 * gibibyte) return { key: '8-16', heading: i18n.t('models.sort.sizeGroups.from8To16') };
        if (bytes < 32 * gibibyte) return { key: '16-32', heading: i18n.t('models.sort.sizeGroups.from16To32') };
        return { key: '32-plus', heading: i18n.t('models.sort.sizeGroups.from32') };
    }

    if (sortKey === 'name') {
        const name = inputArguments.getModelDisplayName(model);
        const key = inputArguments.getNameGroupKey(name);
        if (!key) return { key: null, heading: null };
        return { key, heading: key };
    }

    return { key: null, heading: null };
};

const getSortValue = (inputArguments: { model: ModelPropertyInput; field: string; getModelPlugin: (model: ModelPropertyInput) => string; getModelProvider: (model: ModelPropertyInput) => string; getModelStatus: (model: ModelPropertyInput) => string; getModelDisplayName: (model: ModelPropertyInput) => string }): string | number => {
    const plugin = (inputArguments.getModelPlugin(inputArguments.model) || '').toLowerCase();
    const provider = (inputArguments.getModelProvider(inputArguments.model) || '').toLowerCase();
    const modelObject = isModelObjectInput(inputArguments.model) ? inputArguments.model : null;
    const typeValue = modelObject ? modelObject['type'] : null;
    const type = isString(typeValue) ? typeValue : '';
    const sizeBytesValue = modelObject ? modelObject['sizeBytes'] : null;
    const sizeBytes = typeof sizeBytesValue === 'number' ? sizeBytesValue : 0;
    switch (inputArguments.field) {
        case 'type':
            return type === 'local' ? '0-local' : `1-${type || 'unknown'}`;
        case 'provider':
            return provider;
        case 'plugin':
            return plugin;
        case 'status':
            return inputArguments.getModelStatus(inputArguments.model);
        case 'size':
            return sizeBytes;
        default:
            return inputArguments.getModelDisplayName(inputArguments.model).toLowerCase();
    }
};

export { createModelsModelProperties, extractCleanModelId, formatStrategyLabel, getModelDisplayName, getModelIcon, getModelOriginId, getModelPlugin, getModelProvider, getModelStatus, getSortValue, isModelRecord, resolveGroupHeading, resolveModelEnabledToggleTarget, resolveModelsItemCardId };
export type { ModelEnabledToggleTarget, ModelPropertyInput };

function createModelsModelProperties(dependencies: ModelsModelPropertiesDependencies): {
    getModelPlugin: (model: ModelPropertyInput) => string;
    getModelProvider: (model: ModelPropertyInput) => string;
    getModelOriginId: (model: ModelPropertyInput) => string;
    getModelDisplayName: (model: ModelPropertyInput) => string;
    extractCleanModelId: (id: string) => string;
    getModelIcon: (model: ModelPropertyInput, provider: JsonValue | null | undefined) => TrustedHtml;
    getModelStatus: (statusManager: { normalizeStatus(status: JsonValue | null | undefined): string }, model: ModelPropertyInput) => string;
    canDeleteModel: (model: ModelPropertyInput) => boolean;
    isExternalProviderModel: (model: ModelPropertyInput) => boolean;
    formatStrategyLabel: (strategy: JsonValue | null | undefined) => string;
} {
    const format = (strategy: JsonValue | null | undefined): string => formatStrategyLabel(strategy);
    const getIcon = (model: ModelPropertyInput, provider: JsonValue | null | undefined): TrustedHtml => getModelIcon(dependencies, model, provider);
    const isExternal = (model: ModelPropertyInput): boolean => isModelRecord(model) && isProviderBackedModelRecord(model);
    const canDelete = (model: ModelPropertyInput): boolean => {
        if (!isModelRecord(model)) return false;
        const pluginName = getModelPlugin(model);
        const plugin = pluginName ? dependencies.getPluginByName(pluginName) : null;
        return canDeleteModelRecord(model, plugin);
    };

    return {
        getModelPlugin,
        getModelProvider,
        getModelOriginId,
        getModelDisplayName,
        extractCleanModelId: extractCleanModelRuntimeId,
        getModelIcon: getIcon,
        getModelStatus,
        canDeleteModel: canDelete,
        isExternalProviderModel: isExternal,
        formatStrategyLabel: format
    };
}
