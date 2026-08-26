/* SoAI - Dialog clipboard copy operations [frontend/assets/ts/core/ui/modals/dialogs/clipboardCopy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getClipboardService } from '@core/clipboard.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isClipboardService } from '@core/ui/modals/dialogs/guards.ts';
import { copyTextWithClipboardFeedback } from '@core/ui/notifications/clipboardCopy.ts';
import type { ClipboardServiceInterface } from '@core/ui/modals/dialogs/types.ts';

const resolveClipboardService = (): ClipboardServiceInterface | null => {
    const clipboardService = getClipboardService();
    return isClipboardService(clipboardService) ? clipboardService : null;
};

const copyTextToClipboard = async (value: string, options: { notify: (message: string, type: string) => void; successMessage: string; errorMessage: string; unavailableMessage: string }): Promise<boolean> => {
    const clipboardService = resolveClipboardService();
    if (!clipboardService) {
        options.notify(options.unavailableMessage, 'warning');
        return false;
    }

    try {
        return await copyTextWithClipboardFeedback(
            {
                hasClipboardSupport: () => clipboardService.isSupported() === true,
                copyToClipboard: async (text, copyOptions): Promise<void> => {
                    const clipboardOptions = copyOptions?.notify
                        ? {
                              successMessage: options.successMessage,
                              errorMessage: options.errorMessage,
                              notify: copyOptions.notify
                          }
                        : {
                              successMessage: options.successMessage,
                              errorMessage: options.errorMessage
                          };
                    const copied = await clipboardService.copyText(text, {
                        ...clipboardOptions
                    });
                    if (copied !== true) {
                        throw new Error('Dialogs clipboard copy failed');
                    }
                }
            },
            {
                showNotification: (message, type): void => options.notify(message, type)
            },
            {
                text: value,
                successMessage: options.successMessage,
                errorMessage: options.errorMessage,
                unavailableMessage: options.unavailableMessage,
                unavailableType: 'warning'
            }
        );
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn('Dialogs', 'Copy failed', runtimeError);
    }
    return false;
};

export { copyTextToClipboard, resolveClipboardService };
