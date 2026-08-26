/* SoAI - Chat page control layer DOM empty state [frontend/assets/ts/pages/chat/controllers/page/dom/emptyState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readTrimmedInputValue } from '@core/dom/formValues.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import { isArray } from '@core/typeGuards.ts';
import { updateChatEmptyStateInputHint } from '@pages/chat/controllers/chatUiVisibility.ts';
import type { ChatAttachmentManager } from '@pages/chat/controllers/page/dom/contracts.ts';

const updateEmptyStateInputHint = (host: PageDomOwnerHost, chatInput: HTMLTextAreaElement | null, attachmentManager: ChatAttachmentManager | null): void => {
    const hasTextInput = Boolean(chatInput && readTrimmedInputValue(chatInput).length > 0);
    const attachments = attachmentManager && attachmentManager.getAttachments ? attachmentManager.getAttachments() : [];
    updateChatEmptyStateInputHint(
        {
            pageDom: host.pageDom
        },
        {
            hasTextInput,
            hasAttachments: isArray(attachments) && attachments.length > 0
        }
    );
};

export { updateEmptyStateInputHint };
