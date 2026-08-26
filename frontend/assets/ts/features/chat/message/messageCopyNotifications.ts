/* SoAI - Chat feature message copy notifications [frontend/assets/ts/features/chat/message/messageCopyNotifications.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { copyTextWithHostClipboardFeedback } from '@core/ui/notifications/clipboardCopy.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';

interface CopyActionDependencies {
    showNotification: (message: string, type: NotificationType) => void;
    runWithBoundary: <T>(name: string, functionValue: () => Promise<T>) => Promise<T>;
    hasClipboardSupport: () => boolean;
    copyToClipboard: (text: string, options?: { notify?: (message: string, type: NotificationType) => void }) => Promise<void>;
}

type ChatMessageCopyFeedbackDependencies = Pick<CopyActionDependencies, 'showNotification' | 'hasClipboardSupport' | 'copyToClipboard'>;

const copyChatMessageTextWithFeedback = async (dependencies: ChatMessageCopyFeedbackDependencies, text: string, successMessage?: string | undefined): Promise<void> => {
    const resolvedSuccessMessage = successMessage ?? i18n.t('chat.message.copied');
    await copyTextWithHostClipboardFeedback(
        {
            copyToClipboard: (value, options) => dependencies.copyToClipboard(value, options),
            hasClipboardSupport: () => dependencies.hasClipboardSupport(),
            showNotification: (message, type): void => dependencies.showNotification(message, type)
        },
        {
            text,
            successMessage: resolvedSuccessMessage,
            errorMessage: i18n.t('chat.message.copyFailed'),
            unavailableMessage: i18n.t('chat.message.copyFailed'),
            unavailableType: 'error'
        }
    );
};

const copyTextWithNotification = async (dependencies: CopyActionDependencies, operationId: string, text: string, successMessage: string): Promise<void> => {
    await dependencies.runWithBoundary(operationId, async () => {
        await copyChatMessageTextWithFeedback(dependencies, text, successMessage);
    });
};

export { copyChatMessageTextWithFeedback, copyTextWithNotification };
export type { ChatMessageCopyFeedbackDependencies, CopyActionDependencies };
