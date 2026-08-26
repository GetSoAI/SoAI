/* SoAI - Settings page control layer system manager controller [frontend/assets/ts/pages/settings/controllers/systemmanager/controller.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { executeConfirmedButtonAction } from '@pages/settings/controllers/page/confirmedactionexecution/service.ts';
import { executeConfirmedReset, showResetOperationFailure } from '@pages/settings/controllers/systemmanager/confirmedresetexecution/service.ts';
import { FACTORY_RESET_RELOAD_DELAY_MS } from '@pages/settings/controllers/systemmanager/constants.ts';
import type { FactoryResetExecutionContext, ManagedTimerState, ResetActionExecutionContext } from '@pages/settings/controllers/systemmanager/contracts.ts';
import { refreshWallpaperFromState } from '@pages/settings/controllers/systemmanager/wallpaperStateRefreshController.ts';

const runWithOneShotTimer = (host: ResetActionExecutionContext['host'], state: ManagedTimerState, delayMs: number, onTimeout: () => void): void => {
    if (state.value !== null) {
        host.view.pageResources.clearTimer(state.value);
    }

    state.value = host.view.pageResources.setTimer(() => {
        state.value = null;
        onTimeout();
    }, delayMs);
};

const executeResetPreferences = async ({ host, button }: ResetActionExecutionContext): Promise<void> => {
    return executeConfirmedReset(
        { host, button },
        'settings:resetPreferences',
        {
            title: i18n.t('settings.system.preferencesReset.confirmTitle'),
            message: i18n.t('settings.system.preferencesReset.confirmMessage'),
            confirmText: i18n.t('settings.system.resetButtonLabel'),
            cancelText: i18n.t('common.cancel'),
            variant: 'danger'
        },
        async () => {
            await host.api.resetUiPreferencesRemote();
            host.api.resetUiPreferencesLocal({ preserveWizardState: true });
            refreshWallpaperFromState(host);
        },
        i18n.t('settings.notifications.preferencesResetSuccess'),
        () => i18n.t('settings.notifications.preferencesResetFailed'),
        async () => await host.workflow.refreshSettingsAfterPreferencesReset()
    );
};

const executeResetAclPolicy = async ({ host, button }: ResetActionExecutionContext): Promise<void> => {
    return executeConfirmedReset(
        { host, button },
        'settings:resetAclPolicy',
        {
            title: i18n.t('settings.system.aclPolicyReset.confirmTitle'),
            message: i18n.t('settings.system.aclPolicyReset.confirmMessage'),
            confirmText: i18n.t('settings.system.resetButtonLabel'),
            cancelText: i18n.t('common.cancel'),
            variant: 'danger'
        },
        async () => {
            await host.api.resetAclPolicy();
        },
        i18n.t('settings.notifications.aclPolicyResetSuccess'),
        () => i18n.t('settings.notifications.aclPolicyResetFailed'),
        async () => await host.api.refreshAclPolicyAfterReset()
    );
};

const executeResetAppearance = async ({ host, button }: ResetActionExecutionContext): Promise<void> => {
    return executeConfirmedReset(
        { host, button },
        'settings:resetAppearance',
        {
            title: i18n.t('settings.system.appearanceReset.confirmTitle'),
            message: i18n.t('settings.system.appearanceReset.confirmMessage'),
            confirmText: i18n.t('settings.system.resetButtonLabel'),
            cancelText: i18n.t('common.cancel'),
            variant: 'danger'
        },
        async () => {
            await host.api.resetAppearancePreferences();
            refreshWallpaperFromState(host);
        },
        i18n.t('settings.notifications.appearanceResetSuccess'),
        () => i18n.t('settings.notifications.appearanceResetFailed'),
        async () => await host.workflow.refreshSettingsAfterPreferencesReset()
    );
};

const executeResetMetrics = async ({ host, button }: ResetActionExecutionContext): Promise<void> => {
    return executeConfirmedReset(
        { host, button },
        'settings:resetMetrics',
        {
            title: i18n.t('settings.system.metricsReset.confirmTitle'),
            message: i18n.t('settings.system.metricsReset.confirmMessage'),
            confirmText: i18n.t('settings.system.resetButtonLabel'),
            cancelText: i18n.t('common.cancel'),
            variant: 'danger'
        },
        async () => {
            await host.api.resetMetrics();
        },
        i18n.t('settings.notifications.metricsResetSuccess'),
        () => i18n.t('settings.notifications.metricsResetFailed')
    );
};

const executeResetHardwareHistory = async ({ host, button }: ResetActionExecutionContext): Promise<void> => {
    return executeConfirmedReset(
        { host, button },
        'settings:resetHardwareHistory',
        {
            title: i18n.t('settings.system.hardwareHistoryReset.confirmTitle'),
            message: i18n.t('settings.system.hardwareHistoryReset.confirmMessage'),
            confirmText: i18n.t('settings.system.resetButtonLabel'),
            cancelText: i18n.t('common.cancel'),
            variant: 'danger'
        },
        async () => {
            await host.api.resetHardwareHistory();
        },
        i18n.t('settings.notifications.hardwareHistoryResetSuccess'),
        () => i18n.t('settings.notifications.hardwareHistoryResetFailed')
    );
};

const executeClearPromptHistory = async ({ host, button }: ResetActionExecutionContext): Promise<void> => {
    return executeConfirmedReset(
        { host, button },
        'settings:clearPromptHistory',
        {
            title: i18n.t('settings.system.promptHistoryClear.confirmTitle'),
            message: i18n.t('settings.system.promptHistoryClear.confirmMessage'),
            confirmText: i18n.t('settings.system.promptHistoryClear.button'),
            cancelText: i18n.t('common.cancel'),
            variant: 'danger'
        },
        async () => {
            await host.api.clearPromptHistory();
        },
        i18n.t('chat.promptHistory.cleared'),
        () => i18n.t('chat.promptHistory.clearFailed')
    );
};

const executeResetToolApprovalPermissions = async ({ host, button }: ResetActionExecutionContext): Promise<void> => {
    return executeConfirmedReset(
        { host, button },
        'settings:resetToolApprovalPermissions',
        {
            title: i18n.t('settings.system.toolApprovalPermissionsReset.confirmTitle'),
            message: i18n.t('settings.system.toolApprovalPermissionsReset.confirmMessage'),
            confirmText: i18n.t('settings.system.resetButtonLabel'),
            cancelText: i18n.t('common.cancel'),
            variant: 'danger'
        },
        async () => {
            await host.api.resetToolApprovalPermissions();
        },
        i18n.t('chat.toolApproval.permissionsReset'),
        () => i18n.t('chat.toolApproval.permissionsResetFailed')
    );
};

const executeResetPasswordManager = async ({ host, button }: ResetActionExecutionContext): Promise<void> => {
    let deletedCredentials = 0;
    let clearedSecretHandles = 0;
    await executeConfirmedButtonAction({
        host: host.execution,
        button,
        boundaryName: 'settings:resetPasswordManager',
        confirmOptions: {
            title: i18n.t('settings.system.passwordManagerReset.confirmTitle'),
            message: i18n.t('settings.system.passwordManagerReset.confirmMessage'),
            confirmText: i18n.t('settings.system.resetButtonLabel'),
            cancelText: i18n.t('common.cancel'),
            variant: 'danger'
        },
        action: async (): Promise<null> => {
            const response = await host.api.resetPasswordVault();
            deletedCredentials = response.deletedCredentials;
            clearedSecretHandles = response.clearedSecretHandles;
            return null;
        },
        afterSuccess: () => {
            host.notifications.feedback.show(
                i18n.t('settings.notifications.passwordManagerResetSuccess', {
                    deletedCredentials,
                    clearedSecretHandles
                }),
                'success'
            );
        },
        onError: (error) => {
            const runtimeError = ensureError(error);
            showResetOperationFailure(host, runtimeError, i18n.t('settings.notifications.passwordManagerResetFailed'));
        }
    });
};

const executeConfigurationReset = async ({ host, button }: ResetActionExecutionContext): Promise<void> => {
    await executeConfirmedButtonAction({
        host: host.execution,
        button,
        boundaryName: 'settings:resetConfiguration',
        confirmOptions: {
            title: i18n.t('settings.system.configurationReset.confirmTitle'),
            message: i18n.t('settings.system.configurationReset.confirmMessage'),
            confirmText: i18n.t('settings.system.resetButtonLabel'),
            cancelText: i18n.t('common.cancel'),
            variant: 'danger'
        },
        action: async (): Promise<null> => {
            await host.api.resetConfiguration();
            return null;
        },
        afterSuccess: () => {
            host.workflow.showRestartOverlay('restart-application');
        },
        onActionError: (runtimeError): void => {
            showResetOperationFailure(host, runtimeError, i18n.t('settings.notifications.configurationResetFailed'));
        },
        keepDisabled: true
    });
};

const executeFactoryReset = async ({ host, button, timerState }: FactoryResetExecutionContext): Promise<void> => {
    await host.execution.confirmAndExecute(
        'settings:showFactoryResetConfirmation',
        {
            title: i18n.t('settings.system.factoryReset.confirmModal1.title'),
            message: i18n.t('settings.system.factoryReset.confirmModal1.message'),
            description: i18n.t('settings.system.factoryReset.confirmModal1.description'),
            descriptionAllowHTML: true,
            confirmText: i18n.t('settings.system.resetButtonLabel'),
            cancelText: i18n.t('common.cancel'),
            variant: 'danger'
        },
        async (): Promise<null> => {
            await executeConfirmedButtonAction({
                host: host.execution,
                button,
                boundaryName: 'settings:executeFactoryReset',
                confirmOptions: {
                    title: i18n.t('settings.system.factoryReset.confirmModal2.title'),
                    message: i18n.t('settings.system.factoryReset.confirmModal2.message'),
                    description: i18n.t('settings.system.factoryReset.confirmModal2.description'),
                    descriptionAllowHTML: true,
                    confirmText: i18n.t('settings.system.resetButtonLabel'),
                    cancelText: i18n.t('common.cancel'),
                    variant: 'danger'
                },
                action: async (): Promise<null> => {
                    await host.api.factoryReset();
                    return null;
                },
                successMessage: i18n.t('settings.notifications.factoryResetSuccess'),
                afterSuccess: () => {
                    runWithOneShotTimer(host, timerState, FACTORY_RESET_RELOAD_DELAY_MS, () => {
                        host.workflow.navigate('login', { force: true, replace: true });
                    });
                },
                keepDisabled: true
            });
            return null;
        },
        null,
        null,
        null
    );
};

export { executeClearPromptHistory, executeConfigurationReset, executeFactoryReset, executeResetAclPolicy, executeResetAppearance, executeResetHardwareHistory, executeResetMetrics, executeResetPasswordManager, executeResetPreferences, executeResetToolApprovalPermissions };
