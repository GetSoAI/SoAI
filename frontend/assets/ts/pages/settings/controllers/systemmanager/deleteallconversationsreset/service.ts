/* SoAI - Settings system delete-all-conversations reset action [frontend/assets/ts/pages/settings/controllers/systemmanager/deleteallconversationsreset/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { showOperationFailureNotification } from '@core/ui/notifications/operationFailure.ts';
import { executeConfirmedButtonAction } from '@pages/settings/controllers/page/confirmedactionexecution/service.ts';
import type { ResetActionExecutionContext } from '@pages/settings/controllers/systemmanager/contracts.ts';

const executeDeleteAllConversations = async ({ host, button }: ResetActionExecutionContext): Promise<void> => {
    let deletedCount = 0;
    await executeConfirmedButtonAction({
        host: host.execution,
        button,
        boundaryName: 'settings:deleteAllConversations',
        confirmOptions: {
            title: i18n.t('settings.system.deleteAllConversations.confirmTitle'),
            message: i18n.t('settings.system.deleteAllConversations.confirmMessage'),
            confirmText: i18n.t('settings.system.resetButtonLabel'),
            cancelText: i18n.t('common.cancel'),
            variant: 'danger'
        },
        action: async (): Promise<null> => {
            const response = await host.api.deleteAllConversations();
            deletedCount = response.deleted;
            return null;
        },
        afterSuccess: () => {
            const message =
                deletedCount > 0
                    ? i18n.t('settings.notifications.conversationsDeleteSuccess', {
                          count: deletedCount
                      })
                    : i18n.t('settings.notifications.conversationsDeleteNone');
            host.notifications.feedback.show(message, 'success');
        },
        onError: (error) => {
            const runtimeError = ensureError(error);
            showOperationFailureNotification({
                error: runtimeError,
                notificationMessage: i18n.t('settings.notifications.conversationsDeleteFailed'),
                rawMessage: false,
                showNotification: (message): void => host.notifications.feedback.show(message, 'error')
            });
        }
    });
};

export { executeDeleteAllConversations };
