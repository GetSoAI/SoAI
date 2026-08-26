/* SoAI - Chat feature message info modal service [frontend/assets/ts/features/chat/message/messageinfomodal/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { MESSAGE_INFO_MODAL_ID } from '@features/chat/message/messageinfomodal/constants.ts';
import { replaceCopyButton, resolveMessageInfoContentElements } from '@features/chat/message/messageinfomodal/dom.ts';
import type { ChatMessage, MessageInfoModalDependencies, MessageInfoSectionContent } from '@features/chat/message/messageinfomodal/types.ts';
import { copyTextWithNotification } from '@features/chat/message/messageCopyNotifications.ts';
import { renderSectionContent } from '@features/chat/message/messageinfomodal/view.ts';

class ChatMessageInfoModal {
    readonly #dependencies: MessageInfoModalDependencies;

    constructor(dependencies: MessageInfoModalDependencies) {
        this.#dependencies = dependencies;
    }

    show(message: ChatMessage): void {
        requireModalPresenter().requireElement(MESSAGE_INFO_MODAL_ID);
        this.#render(message);
        requireModalPresenter().open(MESSAGE_INFO_MODAL_ID);
    }

    #resolveMessageInfoSectionContent(message: ChatMessage): MessageInfoSectionContent {
        return renderSectionContent(this.#dependencies, message);
    }

    #bindCopyButton(button: HTMLButtonElement, copyPayload: string | null): void {
        if (!copyPayload) {
            button.disabled = true;
            button.setAttribute('aria-disabled', 'true');
            return;
        }
        const handleCopyClick = (): void => {
            terminateHandledPromise(copyTextWithNotification(this.#dependencies, 'chat:copyMessageInfo', copyPayload, i18n.t('chat.message.infoModal.copied')));
        };
        button.addEventListener('click', handleCopyClick);
    }

    #render(message: ChatMessage): void {
        const { contentElement, copyButton } = resolveMessageInfoContentElements(MESSAGE_INFO_MODAL_ID);
        const sectionContent = this.#resolveMessageInfoSectionContent(message);
        const contentMarkup = toTrustedUiHtml(sectionContent.html);
        dom.setHTML(contentElement, contentMarkup, { escape: false });

        const reboundCopyButton = replaceCopyButton(copyButton);
        this.#bindCopyButton(reboundCopyButton, sectionContent.copyText);
    }
}

export { ChatMessageInfoModal };
export type { MessageInfoModalDependencies };
