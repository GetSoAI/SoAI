/* SoAI - Settings feature external account modal DOM [frontend/assets/ts/features/settings/externalaccounts/externalAccountModalDom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireButtonElement, requireFormElement, requireSelectElement } from '@core/dom/typedElements.ts';
import { createModalElementResolver } from '@core/modals/modalElementResolver.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';

interface ExternalAccountModalElements {
    title: HTMLElement;
    launcher: HTMLElement;
    chooseMailOption: HTMLElement;
    chooseCalendarOption: HTMLElement;
    editor: HTMLElement;
    editorTitle: HTMLElement;
    editorDescription: HTMLElement;
    form: HTMLFormElement;
    summary: HTMLElement;
    status: HTMLElement;
    error: HTMLElement;
    mailSection: HTMLElement;
    calendarSection: HTMLElement;
    mailOauthSection: HTMLElement;
    calendarOauthSection: HTMLElement;
    closeButton: HTMLButtonElement;
    backButton: HTMLButtonElement;
    deleteButton: HTMLButtonElement;
    testButton: HTMLButtonElement;
    syncButton: HTMLButtonElement;
    oauthConnectButton: HTMLButtonElement;
    oauthClearButton: HTMLButtonElement;
    saveButton: HTMLButtonElement;
    authTypeSelect: HTMLSelectElement;
}

const resolveExternalAccountModalElements = (modal: HTMLElement, modalId: string): ExternalAccountModalElements => {
    const resolver = createModalElementResolver(modal, 'External account modal');
    return {
        title: resolver.requireHTMLElement(modalUiSelector(modalId, 'title'), modal),
        launcher: resolver.requireHTMLElement(modalUiSelector(modalId, 'launcher'), modal),
        chooseMailOption: resolver.requireHTMLElement(modalUiSelector(modalId, 'choose-mail'), modal),
        chooseCalendarOption: resolver.requireHTMLElement(modalUiSelector(modalId, 'choose-calendar'), modal),
        editor: resolver.requireHTMLElement(modalUiSelector(modalId, 'editor'), modal),
        editorTitle: resolver.requireHTMLElement(modalUiSelector(modalId, 'editor-title'), modal),
        editorDescription: resolver.requireHTMLElement(modalUiSelector(modalId, 'editor-description'), modal),
        form: requireFormElement(resolver, modalUiSelector(modalId, 'form'), 'External account modal form', modal),
        summary: resolver.requireHTMLElement(modalUiSelector(modalId, 'summary'), modal),
        status: resolver.requireHTMLElement(modalUiSelector(modalId, 'status'), modal),
        error: resolver.requireHTMLElement(modalUiSelector(modalId, 'error'), modal),
        mailSection: resolver.requireHTMLElement(modalUiSelector(modalId, 'mail-section'), modal),
        calendarSection: resolver.requireHTMLElement(modalUiSelector(modalId, 'calendar-section'), modal),
        mailOauthSection: resolver.requireHTMLElement(modalUiSelector(modalId, 'mail-oauth-section'), modal),
        calendarOauthSection: resolver.requireHTMLElement(modalUiSelector(modalId, 'calendar-oauth-section'), modal),
        closeButton: requireButtonElement(resolver, modalUiSelector(modalId, 'close-btn'), 'External account modal close button', modal),
        backButton: requireButtonElement(resolver, modalUiSelector(modalId, 'back-btn'), 'External account modal back button', modal),
        deleteButton: requireButtonElement(resolver, modalUiSelector(modalId, 'delete-btn'), 'External account modal delete button', modal),
        testButton: requireButtonElement(resolver, modalUiSelector(modalId, 'test-btn'), 'External account modal test button', modal),
        syncButton: requireButtonElement(resolver, modalUiSelector(modalId, 'sync-btn'), 'External account modal sync button', modal),
        oauthConnectButton: requireButtonElement(resolver, modalUiSelector(modalId, 'oauth-connect-btn'), 'External account modal OAuth connect button', modal),
        oauthClearButton: requireButtonElement(resolver, modalUiSelector(modalId, 'oauth-clear-btn'), 'External account modal OAuth clear button', modal),
        saveButton: requireButtonElement(resolver, modalUiSelector(modalId, 'save-btn'), 'External account modal save button', modal),
        authTypeSelect: requireSelectElement(resolver, modalUiSelector(modalId, 'auth-type'), 'External account modal auth type select', modal)
    };
};

export { resolveExternalAccountModalElements };
export type { ExternalAccountModalElements };
