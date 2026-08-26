/* SoAI - Chat message edit content validity checks [frontend/assets/ts/features/chat/message/messageEditValidity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { readTrimmedInputValue } from '@core/dom/formValues.ts';
import { hasRemainingEditAttachments } from '@features/chat/message/messageEditAttachmentDom.ts';

const resolveEditedMessageContainer = (textarea: HTMLTextAreaElement): HTMLElement | null => {
    const container = textarea.closest('.chat-message');
    return container instanceof HTMLElement ? container : null;
};

const hasRemainingEditedMessageContent = (textarea: HTMLTextAreaElement, baselineHasNonTextContent: boolean): boolean => {
    if (readTrimmedInputValue(textarea)) {
        return true;
    }
    if (!baselineHasNonTextContent) {
        return false;
    }
    const container = resolveEditedMessageContainer(textarea);
    if (!container) {
        return baselineHasNonTextContent;
    }
    const strip = dom.resolve('.message-edit-attachment-strip', container);
    return strip instanceof HTMLElement ? hasRemainingEditAttachments(container) : baselineHasNonTextContent;
};

export { hasRemainingEditedMessageContent };
