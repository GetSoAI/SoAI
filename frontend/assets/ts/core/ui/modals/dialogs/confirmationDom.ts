/* SoAI - Typed confirmation modal DOM resolver [frontend/assets/ts/core/ui/modals/dialogs/confirmationDom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { CONFIRMATION_UI_TOKENS } from '@core/ui/modals/dialogs/tokens.ts';

type ConfirmationDom = Readonly<{
    titleElement: HTMLElement;
    iconElement: HTMLElement;
    messageElement: HTMLElement;
    descriptionElement: HTMLElement;
    cancelButton: HTMLButtonElement;
    action1Button: HTMLButtonElement;
    action2Button: HTMLButtonElement;
}>;

const resolveConfirmationDom = (modal: HTMLElement, modalId: string): ConfirmationDom => {
    const titleElement = dom.resolve(modalUiSelector(modalId, CONFIRMATION_UI_TOKENS.TITLE), modal);
    const iconElement = dom.resolve(modalUiSelector(modalId, CONFIRMATION_UI_TOKENS.ICON), modal);
    const messageElement = dom.resolve(modalUiSelector(modalId, CONFIRMATION_UI_TOKENS.MESSAGE), modal);
    const descriptionElement = dom.resolve(modalUiSelector(modalId, CONFIRMATION_UI_TOKENS.DESCRIPTION), modal);
    const cancelButton = dom.resolve(modalUiSelector(modalId, CONFIRMATION_UI_TOKENS.CANCEL), modal);
    const action1Button = dom.resolve(modalUiSelector(modalId, CONFIRMATION_UI_TOKENS.ACTION_1), modal);
    const action2Button = dom.resolve(modalUiSelector(modalId, CONFIRMATION_UI_TOKENS.ACTION_2), modal);

    if (!(titleElement instanceof HTMLElement)) {
        throw new Error('Dialogs confirmation modal title element missing');
    }
    if (!(iconElement instanceof HTMLElement)) {
        throw new Error('Dialogs confirmation modal icon element missing');
    }
    if (!(messageElement instanceof HTMLElement)) {
        throw new Error('Dialogs confirmation modal message element missing');
    }
    if (!(descriptionElement instanceof HTMLElement)) {
        throw new Error('Dialogs confirmation modal description element missing');
    }
    if (!(cancelButton instanceof HTMLButtonElement)) {
        throw new Error('Dialogs confirmation modal cancel button missing');
    }
    if (!(action1Button instanceof HTMLButtonElement)) {
        throw new Error('Dialogs confirmation modal action button missing: action-1');
    }
    if (!(action2Button instanceof HTMLButtonElement)) {
        throw new Error('Dialogs confirmation modal action button missing: action-2');
    }

    return Object.freeze({
        titleElement,
        iconElement,
        messageElement,
        descriptionElement,
        cancelButton,
        action1Button,
        action2Button
    });
};

export { resolveConfirmationDom };
export type { ConfirmationDom };
