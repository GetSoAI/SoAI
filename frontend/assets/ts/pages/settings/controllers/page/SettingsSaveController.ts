/* SoAI - Settings page save controller [frontend/assets/ts/pages/settings/controllers/page/SettingsSaveController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { createSaveController, SAVE_HEADER_PRIORITY_PAGE, type SaveController } from '@core/save/public.ts';
import { hasUnsavedChanges, saveSettings } from '@pages/settings/controllers/page/pageActions.ts';
import type { SettingsRuntimeContext } from '@pages/settings/controllers/page/contracts.ts';
import type { SettingsPageState } from '@pages/settings/controllers/page/state.ts';

const SettingsSaveController = (page: SettingsRuntimeContext, state: SettingsPageState): SaveController => {
    return createSaveController({
        admission: state.preferencesAdmission,
        headerContextId: 'settings',
        headerPriority: SAVE_HEADER_PRIORITY_PAGE,
        requestContextLabel: 'Settings save',
        onSaveSettled: () => state.preferencesManager?.syncOcrDirtyState(),
        onSaveComplete: (): void => page.owners.feedback.show(i18n.t('settings.notifications.saveSuccess'), 'success'),
        units: [
            {
                id: 'settings-ocr-language',
                hasChanges: () => state.preferencesManager?.hasOcrChanges() ?? false,
                prepare: () => state.preferencesManager?.prepareOcrSave() ?? { save: () => ({ type: 'stop' }) },
                save: () => state.preferencesManager?.prepareOcrSave().save()
            },
            {
                id: 'settings',
                hasChanges: () => hasUnsavedChanges(state),
                isValid: () => !state.dirtyStateManager?.hasInvalidFields(),
                save: async () => {
                    try {
                        await saveSettings(page, state);
                    } finally {
                        state.preferencesManager?.syncOcrDirtyState();
                    }
                }
            },
            {
                id: 'settings-acl',
                hasChanges: (): boolean => state.aclManager?.hasChanges() ?? false,
                save: () => state.aclManager?.savePolicy()
            },
            {
                id: 'settings-instance-identity',
                hasChanges: (): boolean => state.instanceIdentityManager?.hasChanges() ?? false,
                isValid: (): boolean => state.instanceIdentityManager?.isValid() ?? true,
                save: () => state.instanceIdentityManager?.save()
            },
            {
                id: 'settings-mcp',
                hasChanges: (): boolean => state.mcpManager?.hasPendingChanges() ?? false,
                isValid: (): boolean => state.mcpManager?.arePendingChangesValid() ?? true,
                save: () => state.mcpManager?.savePendingChanges()
            }
        ]
    });
};

export { SettingsSaveController };
