/* SoAI - Plugins feature save flow [frontend/assets/ts/features/plugins/modals/config/saveFlow.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { savePluginConfigChanges } from '@features/plugins/modals/config/operations.ts';
import type { ConfigManagerHost, ConfigurationManager } from '@features/plugins/modals/config/types.ts';

type SavePluginConfigFlowDependencies = {
    host: ConfigManagerHost;
    modalId: string;
    pluginName: string;
    configurationManager: ConfigurationManager;
    isActiveSaveContext: () => boolean;
    clearModifiedStates: () => void;
    onFinalize: () => void;
};

const savePluginConfigFlow = async (dependencies: SavePluginConfigFlowDependencies): Promise<void> => {
    try {
        await savePluginConfigChanges({
            host: dependencies.host,
            modalId: dependencies.modalId,
            pluginName: dependencies.pluginName,
            configurationManager: dependencies.configurationManager,
            isActiveSaveContext: dependencies.isActiveSaveContext,
            clearModifiedStates: dependencies.clearModifiedStates
        });
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('ConfigManager', i18n.t('plugins.notifications.configSaveFailed'), runtimeError);
        dependencies.host.showNotification(i18n.t('plugins.notifications.configSaveFailed'), 'error');
        throw runtimeError;
    } finally {
        dependencies.onFinalize();
    }
};

export { savePluginConfigFlow };
export type { SavePluginConfigFlowDependencies };
