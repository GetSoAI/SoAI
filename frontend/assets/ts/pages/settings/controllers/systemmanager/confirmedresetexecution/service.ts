/* SoAI - Settings system confirmed reset execution helpers [frontend/assets/ts/pages/settings/controllers/systemmanager/confirmedresetexecution/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { showOperationFailureNotification } from '@core/ui/notifications/operationFailure.ts';
import type { ConfirmationOptions } from '@core/ui/modals/dialogs/types.ts';
import { executeConfirmedButtonAction } from '@pages/settings/controllers/page/confirmedactionexecution/service.ts';
import type { ResetActionExecutionContext } from '@pages/settings/controllers/systemmanager/contracts.ts';

const showResetOperationFailure = (host: ResetActionExecutionContext['host'], error: Error, notificationMessage: string | null): void => {
    showOperationFailureNotification({
        error,
        notificationMessage,
        rawMessage: notificationMessage === null,
        showNotification: (message): void => host.notifications.feedback.show(message, 'error')
    });
};

const executeConfirmedReset = async (context: ResetActionExecutionContext, boundaryName: string, confirmOptions: ConfirmationOptions, action: () => Promise<void>, successMessage: string, failureMessage: ((error: Error) => string) | null, afterSuccess: (() => Promise<void> | void) | null = null): Promise<void> => {
    const { host, button } = context;
    await executeConfirmedButtonAction({
        host: host.execution,
        button,
        boundaryName,
        confirmOptions,
        action: async (): Promise<null> => {
            await action();
            return null;
        },
        successMessage,
        afterSuccess,
        onActionError: (runtimeError): void => {
            showResetOperationFailure(host, runtimeError, failureMessage?.(runtimeError) ?? null);
        }
    });
};

export { executeConfirmedReset, showResetOperationFailure };
