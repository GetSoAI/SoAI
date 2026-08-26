/* SoAI - Typed prompt modal DOM resolver [frontend/assets/ts/core/ui/modals/dialogs/promptDom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { PROMPT_UI_TOKENS } from '@core/ui/modals/dialogs/tokens.ts';

type PromptDom = Readonly<{
    titleElement: HTMLElement;
    messageElement: HTMLElement;
    inputElement: HTMLInputElement;
    cancelButton: HTMLButtonElement;
    confirmButton: HTMLButtonElement;
}>;

const resolvePromptDom = (modal: HTMLElement, modalId: string): PromptDom => {
    const titleElement = dom.resolve(modalUiSelector(modalId, PROMPT_UI_TOKENS.TITLE), modal);
    const messageElement = dom.resolve(modalUiSelector(modalId, PROMPT_UI_TOKENS.MESSAGE), modal);
    const inputElement = dom.resolve(modalUiSelector(modalId, PROMPT_UI_TOKENS.INPUT), modal);
    const cancelButton = dom.resolve(modalUiSelector(modalId, PROMPT_UI_TOKENS.CANCEL), modal);
    const confirmButton = dom.resolve(modalUiSelector(modalId, PROMPT_UI_TOKENS.CONFIRM), modal);

    if (!(titleElement instanceof HTMLElement)) {
        throw new Error('Dialogs prompt modal title element missing');
    }
    if (!(messageElement instanceof HTMLElement)) {
        throw new Error('Dialogs prompt modal message element missing');
    }
    if (!(inputElement instanceof HTMLInputElement)) {
        throw new Error('Dialogs prompt modal input element missing');
    }
    if (!(cancelButton instanceof HTMLButtonElement)) {
        throw new Error('Dialogs prompt modal cancel button missing');
    }
    if (!(confirmButton instanceof HTMLButtonElement)) {
        throw new Error('Dialogs prompt modal confirm button missing');
    }

    return Object.freeze({
        titleElement,
        messageElement,
        inputElement,
        cancelButton,
        confirmButton
    });
};

export { resolvePromptDom };
export type { PromptDom };
