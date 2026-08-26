/* SoAI - Plugins feature save controller [frontend/assets/ts/features/plugins/modals/config/saveController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createSaveController, SAVE_HEADER_PRIORITY_MODAL, type SaveController } from '@core/save/public.ts';

interface PluginConfigSaveControllerOptions {
    hasChanges: () => boolean;
    isValid: () => boolean;
    save: () => Promise<void>;
}

const createPluginConfigModalSaveController = (options: PluginConfigSaveControllerOptions): SaveController => {
    return createSaveController({
        headerContextId: 'plugin-config',
        headerPriority: SAVE_HEADER_PRIORITY_MODAL,
        requestContextLabel: 'Plugin config save',
        units: [
            {
                id: 'plugin-config',
                hasChanges: options.hasChanges,
                isValid: options.isValid,
                save: options.save
            }
        ]
    });
};

export { createPluginConfigModalSaveController };
