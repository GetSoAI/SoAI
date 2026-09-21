/* SoAI - Chat model control menu search rendering and filtering [frontend/assets/ts/pages/chat/controllers/chatmodelcontrol/ChatModelControlMenuSearchWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { normalizeSearchDisplayQuery, matchesSearchFilterQuery } from '@core/search/searchQuery.ts';
import type { SanitizerApi } from '@core/pagecontext/public.ts';
import { renderLabelAttributes } from '@core/security/public.ts';
import { renderSearchFieldActions } from '@core/ui/searchField.ts';

const CHAT_MODEL_MENU_SEARCH_INPUT_SELECTOR = '.chat-model-menu-search-input';
const CHAT_MODEL_MENU_OPTION_SELECTOR = '.chat-model-menu-option';
const CHAT_MODEL_MENU_GROUP_SELECTOR = '.chat-model-menu-group';
const CHAT_MODEL_MENU_PRESERVED_SELECTOR = '.chat-model-menu-preserved';
const CHAT_MODEL_MENU_EMPTY_SELECTOR = '.chat-model-menu-empty';

type ChatModelMenuSearchRenderArguments = {
    sanitizer: SanitizerApi;
    query: string;
};

type ChatModelMenuSearchInputState = {
    wasFocused: boolean;
    selectionStart: number | null;
    selectionEnd: number | null;
};

const resolveChatModelMenuSearchQuery = (value: string): string => normalizeSearchDisplayQuery(value);

const renderChatModelMenuSearch = (inputArguments: ChatModelMenuSearchRenderArguments): string => {
    const stringValue = inputArguments.sanitizer;
    const placeholder = i18n.t('chat.modelControl.searchPlaceholder');
    return `<div class="chat-model-menu-search">` + `<div class="searchbar-container searchbar-container--control wide u-stretch">` + `<input type="text" class="searchbar-input chat-model-menu-search-input" value="${stringValue.attribute(inputArguments.query)}" placeholder="${stringValue.attribute(placeholder)}" autocomplete="off" ${renderLabelAttributes(placeholder)}>` + renderSearchFieldActions().html + `</div>` + `</div>`;
};

const renderChatModelMenuEmpty = (inputArguments: { sanitizer: SanitizerApi; hidden: boolean }): string => {
    const hiddenAttr = inputArguments.hidden ? ' hidden' : '';
    return `<div class="chat-model-menu-empty"${hiddenAttr}>${inputArguments.sanitizer.html(i18n.t('chat.modelControl.noSearchResults'))}</div>`;
};

const captureChatModelMenuSearchInputState = (root: HTMLElement): ChatModelMenuSearchInputState | null => {
    const input = dom.resolve(CHAT_MODEL_MENU_SEARCH_INPUT_SELECTOR, root);
    if (!(input instanceof HTMLInputElement)) {
        return null;
    }
    return {
        wasFocused: root.ownerDocument.activeElement === input,
        selectionStart: input.selectionStart,
        selectionEnd: input.selectionEnd
    };
};

const restoreChatModelMenuSearchInputState = (root: HTMLElement, state: ChatModelMenuSearchInputState | null): void => {
    if (state === null || !state.wasFocused) {
        return;
    }
    const input = dom.resolve(CHAT_MODEL_MENU_SEARCH_INPUT_SELECTOR, root);
    if (!(input instanceof HTMLInputElement)) {
        return;
    }
    input.focus({ preventScroll: true });
    if (state.selectionStart !== null && state.selectionEnd !== null) {
        input.setSelectionRange(state.selectionStart, state.selectionEnd);
    }
};

const filterChatModelMenuGroup = (group: Element, query: string): number => {
    let visibleOptions = 0;
    for (const option of dom.resolveAll(CHAT_MODEL_MENU_OPTION_SELECTOR, group)) {
        if (!(option instanceof HTMLElement)) {
            throw new Error('Chat model menu search option must be an HTMLElement');
        }
        const visible = matchesSearchFilterQuery(option.dataset['searchIndex'] ?? option.textContent ?? '', query);
        dom.toggleClass(option, 'u-hidden', !visible);
        if (visible) {
            visibleOptions += 1;
        }
    }
    dom.toggleClass(group, 'u-hidden', visibleOptions === 0);
    return visibleOptions;
};

const applyChatModelMenuSearchFilter = (menu: HTMLElement, query: string): void => {
    let visibleOptions = 0;
    for (const group of dom.resolveAll(CHAT_MODEL_MENU_GROUP_SELECTOR, menu)) {
        visibleOptions += filterChatModelMenuGroup(group, query);
    }
    for (const preserved of dom.resolveAll(CHAT_MODEL_MENU_PRESERVED_SELECTOR, menu)) {
        if (!(preserved instanceof HTMLElement)) {
            throw new Error('Chat model preserved menu entry must be an HTMLElement');
        }
        const option = dom.resolve(CHAT_MODEL_MENU_OPTION_SELECTOR, preserved);
        const visible = option instanceof HTMLElement && matchesSearchFilterQuery(option.dataset['searchIndex'] ?? option.textContent ?? '', query);
        dom.toggleClass(preserved, 'u-hidden', !visible);
        if (visible) {
            visibleOptions += 1;
        }
    }
    const empty = dom.resolve(CHAT_MODEL_MENU_EMPTY_SELECTOR, menu);
    if (empty instanceof HTMLElement) {
        dom.toggleClass(empty, 'u-hidden', query.length === 0 || visibleOptions > 0);
    }
};

const applyChatModelMenuSearchInput = (input: HTMLInputElement): string => {
    const menu = input.closest('.chat-model-menu');
    if (!(menu instanceof HTMLElement)) {
        throw new Error('Chat model menu search input requires an open menu');
    }
    const query = resolveChatModelMenuSearchQuery(input.value);
    applyChatModelMenuSearchFilter(menu, query);
    return query;
};

export { applyChatModelMenuSearchFilter, applyChatModelMenuSearchInput, captureChatModelMenuSearchInputState, CHAT_MODEL_MENU_SEARCH_INPUT_SELECTOR, renderChatModelMenuEmpty, renderChatModelMenuSearch, resolveChatModelMenuSearchQuery, restoreChatModelMenuSearchInputState };
export type { ChatModelMenuSearchInputState };
