/* SoAI - Typed password-change modal DOM resolver [frontend/assets/ts/core/ui/modals/dialogs/passwordChangeDom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireButtonElement, requireInputElement } from '@core/dom/typedElements.ts';
import { createModalElementResolver } from '@core/modals/modalElementResolver.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { PASSWORD_CHANGE_UI_TOKENS } from '@core/ui/modals/dialogs/tokens.ts';

type PasswordChangeDom = Readonly<{
    titleElement: HTMLElement;
    descriptionElement: HTMLElement;
    currentLabel: HTMLElement;
    newLabel: HTMLElement;
    confirmLabel: HTMLElement;
    currentInput: HTMLInputElement;
    newInput: HTMLInputElement;
    confirmInput: HTMLInputElement;
    errorElement: HTMLElement;
    cancelButton: HTMLButtonElement;
    submitButton: HTMLButtonElement;
}>;

const resolvePasswordChangeDom = (modal: HTMLElement, modalId: string): PasswordChangeDom => {
    const resolver = createModalElementResolver(modal, 'Password change modal');
    return Object.freeze({
        titleElement: resolver.requireHTMLElement(modalUiSelector(modalId, PASSWORD_CHANGE_UI_TOKENS.TITLE)),
        descriptionElement: resolver.requireHTMLElement(modalUiSelector(modalId, PASSWORD_CHANGE_UI_TOKENS.DESCRIPTION)),
        currentLabel: resolver.requireHTMLElement(modalUiSelector(modalId, PASSWORD_CHANGE_UI_TOKENS.CURRENT_LABEL)),
        newLabel: resolver.requireHTMLElement(modalUiSelector(modalId, PASSWORD_CHANGE_UI_TOKENS.NEW_LABEL)),
        confirmLabel: resolver.requireHTMLElement(modalUiSelector(modalId, PASSWORD_CHANGE_UI_TOKENS.CONFIRM_NEW_LABEL)),
        currentInput: requireInputElement(resolver, modalUiSelector(modalId, PASSWORD_CHANGE_UI_TOKENS.CURRENT), 'Current password input'),
        newInput: requireInputElement(resolver, modalUiSelector(modalId, PASSWORD_CHANGE_UI_TOKENS.NEW), 'New password input'),
        confirmInput: requireInputElement(resolver, modalUiSelector(modalId, PASSWORD_CHANGE_UI_TOKENS.CONFIRM_NEW), 'Confirm password input'),
        errorElement: resolver.requireHTMLElement(modalUiSelector(modalId, PASSWORD_CHANGE_UI_TOKENS.ERROR)),
        cancelButton: requireButtonElement(resolver, modalUiSelector(modalId, PASSWORD_CHANGE_UI_TOKENS.CANCEL), 'Password modal cancel button'),
        submitButton: requireButtonElement(resolver, modalUiSelector(modalId, PASSWORD_CHANGE_UI_TOKENS.SUBMIT), 'Password modal submit button')
    });
};

export { resolvePasswordChangeDom };
export type { PasswordChangeDom };
