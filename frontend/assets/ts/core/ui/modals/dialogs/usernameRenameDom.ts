/* SoAI - Typed username-rename modal DOM resolver [frontend/assets/ts/core/ui/modals/dialogs/usernameRenameDom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireButtonElement, requireInputElement } from '@core/dom/typedElements.ts';
import { createModalElementResolver } from '@core/modals/modalElementResolver.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { USERNAME_RENAME_UI_TOKENS } from '@core/ui/modals/dialogs/tokens.ts';

type UsernameRenameDom = Readonly<{
    titleElement: HTMLElement;
    descriptionElement: HTMLElement;
    usernameLabel: HTMLElement;
    usernameInput: HTMLInputElement;
    passwordLabel: HTMLElement;
    passwordInput: HTMLInputElement;
    errorElement: HTMLElement;
    cancelButton: HTMLButtonElement;
    submitButton: HTMLButtonElement;
}>;

const resolveUsernameRenameDom = (modal: HTMLElement, modalId: string): UsernameRenameDom => {
    const resolver = createModalElementResolver(modal, 'Username rename modal');
    return Object.freeze({
        titleElement: resolver.requireHTMLElement(modalUiSelector(modalId, USERNAME_RENAME_UI_TOKENS.TITLE)),
        descriptionElement: resolver.requireHTMLElement(modalUiSelector(modalId, USERNAME_RENAME_UI_TOKENS.DESCRIPTION)),
        usernameLabel: resolver.requireHTMLElement(modalUiSelector(modalId, USERNAME_RENAME_UI_TOKENS.USERNAME_LABEL)),
        usernameInput: requireInputElement(resolver, modalUiSelector(modalId, USERNAME_RENAME_UI_TOKENS.USERNAME), 'Rename username input'),
        passwordLabel: resolver.requireHTMLElement(modalUiSelector(modalId, USERNAME_RENAME_UI_TOKENS.PASSWORD_LABEL)),
        passwordInput: requireInputElement(resolver, modalUiSelector(modalId, USERNAME_RENAME_UI_TOKENS.PASSWORD), 'Rename password input'),
        errorElement: resolver.requireHTMLElement(modalUiSelector(modalId, USERNAME_RENAME_UI_TOKENS.ERROR)),
        cancelButton: requireButtonElement(resolver, modalUiSelector(modalId, USERNAME_RENAME_UI_TOKENS.CANCEL), 'Rename cancel button'),
        submitButton: requireButtonElement(resolver, modalUiSelector(modalId, USERNAME_RENAME_UI_TOKENS.SUBMIT), 'Rename submit button')
    });
};

export { resolveUsernameRenameDom };
export type { UsernameRenameDom };
