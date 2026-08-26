/* SoAI - Chat message edit DOM transforms [frontend/assets/ts/features/chat/message/messageEditDom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { dom } from '@core/dom/dom.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { createEditAttachmentStrip, renderEditTextareaMarkup } from '@features/chat/message/messageEditAttachmentDom.ts';

type RestoreRenderedMessageTextArguments = {
    container: HTMLElement;
    message: ChatMessage;
    renderMessageTextContent: (message: ChatMessage) => string;
    postRender: (container: Element | null) => void;
};

const beginMessageTextEditing = (container: HTMLElement, editableText: string, removeIcon: TrustedHtml): HTMLTextAreaElement | null => {
    const messageTextNode = dom.resolve('.message-text', container);
    if (!(messageTextNode instanceof HTMLElement)) {
        return null;
    }
    const attachmentStrip = createEditAttachmentStrip(messageTextNode, removeIcon);
    dom.setHTML(messageTextNode, renderEditTextareaMarkup(attachmentStrip), { escape: false });
    const textarea = dom.resolve('textarea', messageTextNode);
    if (!(textarea instanceof HTMLTextAreaElement)) {
        return null;
    }
    textarea.value = editableText;
    textarea.defaultValue = editableText;
    textarea.focus();
    textarea.setSelectionRange(textarea.value.length, textarea.value.length);
    container.classList.add('is-editing');
    return textarea;
};

const restoreRenderedMessageText = (inputArguments: RestoreRenderedMessageTextArguments): void => {
    inputArguments.container.classList.remove('is-editing');
    const messageTextNode = dom.resolve('.message-text', inputArguments.container);
    if (!(messageTextNode instanceof HTMLElement)) {
        return;
    }
    const textHtml = inputArguments.renderMessageTextContent(inputArguments.message);
    const trusted = toTrustedUiHtml(textHtml);
    dom.setHTML(messageTextNode, trusted, { escape: false });
    inputArguments.postRender(messageTextNode);
};

export { beginMessageTextEditing, restoreRenderedMessageText };
