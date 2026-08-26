/* SoAI - Chat page copy code block [frontend/assets/ts/pages/chat/controllers/page/actions/copyCodeBlock.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { copyTextWithHostClipboardFeedback } from '@core/ui/notifications/clipboardCopy.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

interface CopyCodeBlockHost extends PageFeedbackOwnerHost {
    hasClipboardSupport(): boolean;
    copyToClipboard(
        text: string,
        options?: {
            notify?: (message: string, type: NotificationType) => void;
        }
    ): Promise<void>;
}

type CopyCodeBlockOptions = {
    preferMarkdown?: boolean;
};

const resolveCodeBlockClipboardText = (button: Element, options?: CopyCodeBlockOptions): string | null => {
    const encodedMarkdown = button.getAttribute('data-code-markdown');
    if (options?.preferMarkdown === true && encodedMarkdown) {
        return decodeURIComponent(encodedMarkdown);
    }
    const encodedCode = button.getAttribute('data-code');
    if (!encodedCode) {
        return null;
    }
    return decodeURIComponent(encodedCode);
};

const copyCodeBlock = async (host: CopyCodeBlockHost, button: Element, options?: CopyCodeBlockOptions): Promise<void> => {
    const decoded = resolveCodeBlockClipboardText(button, options);
    if (decoded === null) {
        return;
    }
    await copyTextWithHostClipboardFeedback(
        {
            copyToClipboard: (text, copyOptions) => host.copyToClipboard(text, copyOptions),
            hasClipboardSupport: () => host.hasClipboardSupport(),
            showNotification: (message, type): void => host.feedback.show(message, type)
        },
        {
            text: decoded,
            successMessage: i18n.t('chat.message.copied'),
            errorMessage: i18n.t('chat.message.copyFailed'),
            unavailableMessage: i18n.t('chat.message.copyFailed'),
            unavailableType: 'error',
            blurElement: button instanceof HTMLElement ? button : null
        }
    );
};

export { copyCodeBlock };
export type { CopyCodeBlockHost, CopyCodeBlockOptions };
