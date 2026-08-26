/* SoAI - Chat page inline media reference copy controller [frontend/assets/ts/pages/chat/controllers/page/actions/inlineMediaReferenceCopyController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { copyTextWithHostClipboardFeedback } from '@core/ui/notifications/clipboardCopy.ts';
import { stripPreviewReferenceTokensForClipboard } from '@features/chat/public.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

interface CopyInlineMediaReferenceHost extends PageFeedbackOwnerHost {
    hasClipboardSupport(): boolean;
    copyToClipboard(
        text: string,
        options?: {
            notify?: (message: string, type: NotificationType) => void;
        }
    ): Promise<void>;
}

const copyInlineMediaReference = async (host: CopyInlineMediaReferenceHost, actionElement: Element): Promise<void> => {
    const rawValue = actionElement.getAttribute('data-inline-media-copy-value') ?? '';
    const value = toTrimmedString(stripPreviewReferenceTokensForClipboard(toTrimmedString(rawValue)));
    if (!value) {
        return;
    }
    await copyTextWithHostClipboardFeedback(
        {
            copyToClipboard: (text, copyOptions) => host.copyToClipboard(text, copyOptions),
            hasClipboardSupport: () => host.hasClipboardSupport(),
            showNotification: (message, type): void => host.feedback.show(message, type)
        },
        {
            text: value,
            successMessage: i18n.t('common.clipboard.copied'),
            errorMessage: i18n.t('common.clipboard.copyFailed'),
            unavailableMessage: i18n.t('common.clipboard.copyFailed'),
            unavailableType: 'error',
            blurElement: actionElement instanceof HTMLElement ? actionElement : null
        }
    );
};

export { copyInlineMediaReference };
export type { CopyInlineMediaReferenceHost };
