/* SoAI - Models feature plugin availability [frontend/assets/ts/features/models/modals/downloadmodal/pluginAvailability.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { toTrimmedLower, toTrimmedString, toTrimmedUpper } from '@core/normalize.ts';
import { PROVIDER_MODE, hasExplicitProviderMode, resolveProviderMode } from '@core/plugins/providerMode.ts';
import { PLUGIN_STATUS_BACKEND_INSTALLING, PLUGIN_STATUS_BACKEND_NOT_INSTALLED, PLUGIN_STATUS_BACKEND_UPDATING, PLUGIN_STATUS_DELETE_ERROR, PLUGIN_STATUS_DISABLED, PLUGIN_STATUS_INCOMPATIBLE, PLUGIN_STATUS_INSTALL_ERROR, PLUGIN_STATUS_LOAD_ERROR, PLUGIN_STATUS_QUARANTINED, PLUGIN_STATUS_BACKEND_UNINSTALL_ERROR, PLUGIN_STATUS_UPDATE_ERROR } from '@core/state/pluginStatus.ts';
import { isObject } from '@core/typeGuards.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { DownloadModalHost } from '@features/models/modals/downloadmodal/downloadModalTypes.ts';

type PluginUnavailableMode = 'download' | 'provider';

const locatePluginByName = (host: DownloadModalHost, name: string): PluginRecord | null => {
    if (!name) {
        return null;
    }
    const directMatch = host.catalog.getPluginByName(name);
    if (directMatch) {
        return directMatch;
    }
    const normalizedName = toTrimmedLower(name);
    for (const plugin of host.execution.getAvailablePlugins()) {
        if (toTrimmedLower(plugin.name) === normalizedName) {
            return plugin;
        }
    }
    return null;
};

const getPluginDisplayName = (plugin: PluginRecord): string => {
    if (plugin.displayName) {
        return plugin.displayName;
    }
    return plugin.name ?? '';
};

const resolvePluginUnavailableReason = (plugin: PluginRecord | null, mode: PluginUnavailableMode): string => {
    if (!plugin) {
        return i18n.t('models.modal.pluginUnavailableReason.unavailable');
    }
    const compatibility = isObject(plugin.compatibility) ? plugin.compatibility : null;
    const compatibilityReason = compatibility && compatibility['reason'] ? toTrimmedString(compatibility['message']) : '';
    if (compatibilityReason) {
        return compatibilityReason;
    }
    const disabledReason = toTrimmedString(plugin.disabledReason);
    if (disabledReason) {
        return disabledReason;
    }
    const state = toTrimmedUpper(plugin['state']);
    switch (state) {
        case PLUGIN_STATUS_BACKEND_NOT_INSTALLED:
            if (mode === 'provider') {
                break;
            }
            return i18n.t('models.modal.pluginUnavailableReason.backendNotInstalled');
        case PLUGIN_STATUS_BACKEND_INSTALLING:
            if (mode === 'provider') {
                break;
            }
            return i18n.t('models.modal.pluginUnavailableReason.backendInstalling');
        case PLUGIN_STATUS_BACKEND_UPDATING:
            if (mode === 'provider') {
                break;
            }
            return i18n.t('models.modal.pluginUnavailableReason.backendUpdating');
        case PLUGIN_STATUS_INSTALL_ERROR:
            if (mode === 'provider') {
                break;
            }
            return i18n.t('models.modal.pluginUnavailableReason.installError');
        case PLUGIN_STATUS_LOAD_ERROR:
            return i18n.t('models.modal.pluginUnavailableReason.loadError');
        case PLUGIN_STATUS_UPDATE_ERROR:
            return i18n.t('models.modal.pluginUnavailableReason.updateError');
        case PLUGIN_STATUS_BACKEND_UNINSTALL_ERROR:
            return i18n.t('models.modal.pluginUnavailableReason.backendUninstallError');
        case PLUGIN_STATUS_DELETE_ERROR:
            return i18n.t('models.modal.pluginUnavailableReason.deleteError');
        case PLUGIN_STATUS_INCOMPATIBLE:
            return i18n.t('models.modal.pluginUnavailableReason.incompatible');
        case PLUGIN_STATUS_DISABLED:
            return i18n.t('models.modal.pluginUnavailableReason.disabled');
        case PLUGIN_STATUS_QUARANTINED:
            return i18n.t('models.modal.pluginUnavailableReason.quarantined');
        case 'NOT_DETECTED':
            return i18n.t('models.modal.pluginUnavailableReason.notDetected');
        case 'ABSENT':
            return i18n.t('models.modal.pluginUnavailableReason.absent');
        case 'DELETING':
            return i18n.t('models.modal.pluginUnavailableReason.deleting');
        case 'REMOVING_BACKEND':
            return i18n.t('models.modal.pluginUnavailableReason.removing');
        default:
            break;
    }
    if (plugin.isEnabled === false) {
        return i18n.t('models.modal.pluginUnavailableReason.disabled');
    }
    if (plugin.isAvailable === false) {
        return i18n.t('models.modal.pluginUnavailableReason.unavailable');
    }
    const capabilities = isObject(plugin['capabilities']) ? plugin['capabilities'] : null;
    if (mode === 'download' && capabilities?.supportsModelDownload !== true) {
        return i18n.t('models.modal.pluginUnavailableReason.downloadUnsupported');
    }
    if (mode === 'provider') {
        const providerMode = resolveProviderMode(plugin);
        if (hasExplicitProviderMode(plugin) && providerMode !== PROVIDER_MODE.USER_MANAGED) {
            return i18n.t('models.modal.pluginUnavailableReason.providerUnsupported');
        }
        if (capabilities?.supportsProviderManagement === false) {
            return i18n.t('models.modal.pluginUnavailableReason.providerUnsupported');
        }
    }
    return i18n.t('models.modal.pluginUnavailableReason.unavailable');
};

export { getPluginDisplayName, locatePluginByName, resolvePluginUnavailableReason };
export type { PluginUnavailableMode };
