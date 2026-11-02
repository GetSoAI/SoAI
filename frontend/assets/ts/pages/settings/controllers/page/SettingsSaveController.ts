/* SoAI - Settings page save controller [frontend/assets/ts/pages/settings/controllers/page/SettingsSaveController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isPresentationOwnerMutationAllowed } from '@core/presentationOwner.ts';
import { i18n } from '@core/i18n/index.ts';
import { createSaveController, SAVE_HEADER_PRIORITY_PAGE, type SaveController } from '@core/save/public.ts';
import { hasUnsavedChanges, prepareSettingsSave, saveSettings, type PreparedSettingsSave } from '@pages/settings/controllers/page/pageActions.ts';
import type { SettingsRuntimeContext } from '@pages/settings/controllers/page/contracts.ts';
import type { SettingsPageState } from '@pages/settings/controllers/page/state.ts';

const SettingsSaveController = (page: SettingsRuntimeContext, state: SettingsPageState): SaveController => {
    const epoch = page.owners.auth.authEpoch;
    const owner = page.owners.pageContext.presentationOwner;
    const isCurrent = (): boolean => page.owners.auth.authEpoch === epoch && !page.controls.isDestroyed() && isPresentationOwnerMutationAllowed(owner);
    const savePreparedSettings = async (prepared?: PreparedSettingsSave) => {
        try {
            return await saveSettings(page, state, prepared);
        } finally {
            if (isCurrent()) state.preferencesManager?.syncOcrDirtyState();
        }
    };
    return createSaveController({
        owner,
        isCurrent,
        admission: state.preferencesAdmission,
        isDestructionBlocked: () => !state.preferencesAdmission.canAcquire(),
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
                getProtectionRevision: () => JSON.stringify([state.configManager?.protectionRevision ?? 0, state.uiPrefsManager?.protectionRevision ?? 0, state.dirtyStateManager?.protectionRevision ?? 0]),
                hasChanges: () => hasUnsavedChanges(state),
                isValid: () => !state.dirtyStateManager?.hasInvalidFields(),
                prepare: () => {
                    const prepared = prepareSettingsSave(page, state);
                    return { isValid: prepared.isCurrent, save: () => savePreparedSettings(prepared) };
                },
                save: () => savePreparedSettings()
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
