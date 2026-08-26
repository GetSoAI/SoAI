/* SoAI - Character map modal DOM resolution [frontend/assets/ts/pages/chat/controllers/modals/charactermap/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { modalUiSelector } from '@core/modals/uiIds.ts';
import { dom } from '@core/dom/dom.ts';
import { CHARACTER_MAP_ACTIONS, CHAT_CHARACTER_MAP_MODAL_ID } from '@features/chat/public.ts';
import type { CharacterMapModalRefs } from '@pages/chat/controllers/modals/charactermap/types.ts';

const requireElement = <T extends HTMLElement>(modal: HTMLElement, selector: string, constructor: new (...inputArguments: never[]) => T, label: string): T => {
    const element = dom.resolve(selector, modal);
    if (!(element instanceof constructor)) throw new Error(`Character-map ${label} is unavailable`);
    return element;
};

const requireUiElement = <T extends HTMLElement>(modal: HTMLElement, token: string, constructor: new (...inputArguments: never[]) => T, label: string): T => requireElement(modal, modalUiSelector(CHAT_CHARACTER_MAP_MODAL_ID, token), constructor, label);

const resolveCharacterMapModalRefs = (modal: HTMLElement): CharacterMapModalRefs => ({
    modal,
    search: requireUiElement(modal, 'search', HTMLInputElement, 'search field'),
    searchButton: requireElement(modal, `[data-action="${CHARACTER_MAP_ACTIONS.SEARCH}"]`, HTMLButtonElement, 'search action'),
    font: requireUiElement(modal, 'font', HTMLSelectElement, 'font selector'),
    subset: requireUiElement(modal, 'subset', HTMLSelectElement, 'subset selector'),
    loading: requireUiElement(modal, 'loading', HTMLElement, 'loading state'),
    error: requireUiElement(modal, 'error', HTMLElement, 'error state'),
    retry: requireElement(modal, `[data-action="${CHARACTER_MAP_ACTIONS.RETRY}"]`, HTMLButtonElement, 'retry action'),
    empty: requireUiElement(modal, 'empty', HTMLElement, 'empty state'),
    grid: requireUiElement(modal, 'grid', HTMLElement, 'grid'),
    status: requireUiElement(modal, 'status', HTMLElement, 'status'),
    codePoints: requireUiElement(modal, 'code-points', HTMLElement, 'code-point details'),
    name: requireUiElement(modal, 'name', HTMLElement, 'name details'),
    staging: requireUiElement(modal, 'staging', HTMLInputElement, 'staging field'),
    select: requireUiElement(modal, 'select', HTMLButtonElement, 'select action'),
    copy: requireUiElement(modal, 'copy', HTMLButtonElement, 'copy action'),
    insert: requireUiElement(modal, 'insert', HTMLButtonElement, 'insert action')
});

export { resolveCharacterMapModalRefs };
