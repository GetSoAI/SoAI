/* SoAI - Shared search field actions and clear interaction [frontend/assets/ts/core/ui/searchField.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { resolveOptionalKernelService } from '@core/runtime/runtimeContext.ts';
import { type TrustedHtml } from '@core/security/public.ts';
import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { createIconSlot } from '@core/ui/icons/view.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';

const SEARCH_FIELD_CLEAR_ATTRIBUTE = 'data-searchbar-clear';
const SEARCH_FIELD_CLEAR_SELECTOR = `[${SEARCH_FIELD_CLEAR_ATTRIBUTE}]`;

const searchFieldActionClass = (baseClass: string, className: string): string => `${baseClass}${className.trim() ? ` ${className.trim()}` : ''}`;

const renderSearchFieldActions = (className: string = ''): TrustedHtml => {
    const clearLabel = i18n.t('common.search.clear');
    const searchClass = searchFieldActionClass('searchbar-icon', className);
    const clearClass = searchFieldActionClass('searchbar-clear', className);
    return uiHtml`<span class="${uiAttr(searchClass)}" aria-hidden="true">${getIconSync('search', { size: 16, strokeWidth: 1.5 })}</span><button type="button" class="${uiAttr(clearClass)}" ${SEARCH_FIELD_CLEAR_ATTRIBUTE} aria-label="${uiAttr(clearLabel)}" data-tooltip="${uiAttr(clearLabel)}">${getIconSync('close', { size: 16, strokeWidth: 1.5 })}</button>`;
};

const createSearchFieldActions = (documentRef: Document, className: string = ''): readonly HTMLElement[] => {
    const searchIcon = createIconSlot(documentRef, getIconSync('search', { size: 16, strokeWidth: 1.5 }), { className: searchFieldActionClass('searchbar-icon', className) });
    searchIcon.setAttribute('aria-hidden', 'true');
    const clearButton = documentRef.createElement('button');
    clearButton.type = 'button';
    clearButton.className = searchFieldActionClass('searchbar-clear', className);
    clearButton.setAttribute(SEARCH_FIELD_CLEAR_ATTRIBUTE, '');
    const clearLabel = i18n.t('common.search.clear');
    clearButton.setAttribute('aria-label', clearLabel);
    setTooltipText(clearButton, clearLabel);
    clearButton.appendChild(createIconSlot(documentRef, getIconSync('close', { size: 16, strokeWidth: 1.5 })));
    return [searchIcon, clearButton];
};

const resolveSearchFieldClearButton = (event: Event): HTMLButtonElement | null => {
    const target = event.target;
    if (!(target instanceof Element)) return null;
    const button = target.closest(SEARCH_FIELD_CLEAR_SELECTOR);
    if (!button) return null;
    if (!(button instanceof HTMLButtonElement)) throw new TypeError('Search field clear action must be a button');
    return button;
};

const clearSearchField = (button: HTMLButtonElement): void => {
    const container = button.closest('.searchbar-container');
    if (!(container instanceof HTMLElement) || container.classList.contains('header-search')) {
        throw new Error('Search field clear action requires a non-header searchbar container');
    }
    const input = dom.resolve('.searchbar-input', container);
    if (!(input instanceof HTMLInputElement)) throw new TypeError('Search field clear action requires an input');
    if (input.value.length === 0) return;
    input.value = '';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.focus({ preventScroll: true });
};

interface SearchFieldActionService {
    initialize(): void;
    destroy(): void;
}

class SearchFieldActionController implements SearchFieldActionService {
    readonly #documentRef: Document;
    #abortController: AbortController | null = null;

    constructor(documentRef: Document) {
        this.#documentRef = documentRef;
    }

    initialize(): void {
        if (this.#abortController) return;
        const abortController = new AbortController();
        this.#documentRef.addEventListener('click', this.#handleClick, { signal: abortController.signal, capture: true });
        this.#abortController = abortController;
    }

    destroy(): void {
        this.#abortController?.abort('search-field-actions-destroyed');
        this.#abortController = null;
    }

    readonly #handleClick = (event: Event): void => {
        if (event instanceof MouseEvent && event.button !== 0) return;
        const button = resolveSearchFieldClearButton(event);
        if (!button) return;
        event.preventDefault();
        clearSearchField(button);
    };
}

const createSearchFieldActionService = (documentRef: Document): SearchFieldActionService => new SearchFieldActionController(documentRef);

const resetSearchFieldActionService = (): void => {
    const candidate = resolveOptionalKernelService('core.searchFieldActions');
    if (candidate && 'destroy' in candidate && typeof candidate.destroy === 'function') candidate.destroy();
};

export { createSearchFieldActions, createSearchFieldActionService, renderSearchFieldActions, resetSearchFieldActionService };
export type { SearchFieldActionService };
