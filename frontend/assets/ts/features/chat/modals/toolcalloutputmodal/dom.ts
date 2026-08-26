/* SoAI - Chat feature tool call output modal DOM contracts [frontend/assets/ts/features/chat/modals/toolcalloutputmodal/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { narrowButton, narrowHTMLElement } from '@core/dom/narrowElement.ts';
import { rebindButton } from '@core/dom/rebindButton.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import type { ToolCallOutputModalContentElements } from '@features/chat/modals/toolcalloutputmodal/types.ts';

const resolveToolCallOutputModalContentElements = (modalId: string): ToolCallOutputModalContentElements => {
    const modalElement = dom.resolve(`#${modalId}`);
    if (!modalElement) {
        throw new Error('ChatToolCallOutputModal modal element missing');
    }
    const modalRoot = narrowHTMLElement(modalElement, 'ChatToolCallOutputModal modal element');

    const contentElement = dom.resolve(modalUiSelector(modalId, 'content'), modalRoot);
    if (!contentElement) {
        throw new Error('ChatToolCallOutputModal content element missing');
    }

    const copyButton = dom.resolve(modalUiSelector(modalId, 'copy'), modalRoot);
    if (!copyButton) {
        throw new Error('ChatToolCallOutputModal copy button missing');
    }

    return {
        contentElement: narrowHTMLElement(contentElement, 'ChatToolCallOutputModal content element'),
        copyButton: narrowButton(copyButton, 'ChatToolCallOutputModal copy button')
    };
};

const replaceCopyButton = (button: HTMLButtonElement): HTMLButtonElement => {
    return rebindButton(button, 'ChatToolCallOutputModal failed to rebind copy button');
};

export { replaceCopyButton, resolveToolCallOutputModalContentElements };
