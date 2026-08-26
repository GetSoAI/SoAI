/* SoAI - Chat feature message info modal DOM contracts [frontend/assets/ts/features/chat/message/messageinfomodal/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { rebindButton } from '@core/dom/rebindButton.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import type { MessageInfoContentElements } from '@features/chat/message/messageinfomodal/types.ts';

const resolveMessageInfoContentElements = (modalId: string): MessageInfoContentElements => {
    const modalElement = dom.resolve(`#${modalId}`);
    if (!(modalElement instanceof HTMLElement)) {
        throw new Error('ChatMessageInfoModal modal element missing');
    }

    const contentElement = dom.resolve(modalUiSelector(modalId, 'content'), modalElement);
    if (!(contentElement instanceof HTMLElement)) {
        throw new Error('ChatMessageInfoModal content element missing');
    }

    const copyButton = dom.resolve(modalUiSelector(modalId, 'copy'), modalElement);
    if (!(copyButton instanceof HTMLButtonElement)) {
        throw new Error('ChatMessageInfoModal copy button missing');
    }

    return {
        contentElement,
        copyButton
    };
};

const replaceCopyButton = (button: HTMLButtonElement): HTMLButtonElement => {
    return rebindButton(button, 'ChatMessageInfoModal failed to rebind copy button');
};

export { replaceCopyButton, resolveMessageInfoContentElements };
