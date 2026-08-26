/* SoAI - Settings system local reset actions [frontend/assets/ts/pages/settings/controllers/systemmanager/localresetactions/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { publishChatPresetLibraryInvalidation } from '@core/chat/chatPresetLibraryInvalidation.ts';
import { executeConfirmedReset } from '@pages/settings/controllers/systemmanager/confirmedresetexecution/service.ts';
import type { ResetActionExecutionContext } from '@pages/settings/controllers/systemmanager/contracts.ts';

const executeResetChatPresets = async ({ host, button }: ResetActionExecutionContext): Promise<void> => {
    return executeConfirmedReset(
        { host, button },
        'settings:resetChatPresets',
        {
            title: i18n.t('settings.system.chatPresetsReset.confirmTitle'),
            message: i18n.t('settings.system.chatPresetsReset.confirmMessage'),
            confirmText: i18n.t('settings.system.resetButtonLabel'),
            cancelText: i18n.t('common.cancel'),
            variant: 'danger'
        },
        async () => {
            await host.api.resetChatPresets();
            publishChatPresetLibraryInvalidation(true);
        },
        i18n.t('settings.notifications.chatPresetsResetSuccess'),
        () => i18n.t('settings.notifications.chatPresetsResetFailed')
    );
};

const executeResetRecentSearches = async ({ host, button }: ResetActionExecutionContext): Promise<void> => {
    return executeConfirmedReset(
        { host, button },
        'settings:resetRecentSearches',
        {
            title: i18n.t('settings.system.recentSearchesReset.confirmTitle'),
            message: i18n.t('settings.system.recentSearchesReset.confirmMessage'),
            confirmText: i18n.t('settings.system.resetButtonLabel'),
            cancelText: i18n.t('common.cancel'),
            variant: 'danger'
        },
        async () => {
            host.api.resetRecentSearches();
        },
        i18n.t('settings.notifications.recentSearchesResetSuccess'),
        () => i18n.t('settings.notifications.recentSearchesResetFailed')
    );
};

const executeResetMovablePageLayouts = async ({ host, button }: ResetActionExecutionContext): Promise<void> => {
    return executeConfirmedReset(
        { host, button },
        'settings:resetMovablePageLayouts',
        {
            title: i18n.t('settings.system.pageLayoutsReset.confirmTitle'),
            message: i18n.t('settings.system.pageLayoutsReset.confirmMessage'),
            confirmText: i18n.t('settings.system.resetButtonLabel'),
            cancelText: i18n.t('common.cancel'),
            variant: 'danger'
        },
        async () => {
            host.api.resetMovablePageLayouts();
        },
        i18n.t('settings.notifications.pageLayoutsResetSuccess'),
        () => i18n.t('settings.notifications.pageLayoutsResetFailed')
    );
};

export { executeResetChatPresets, executeResetMovablePageLayouts, executeResetRecentSearches };
