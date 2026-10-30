/* SoAI - Controls feature searchbar service [frontend/assets/ts/features/controls/searchbar/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getDocument } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { setSearchFieldLoading } from '@core/ui/searchField.ts';
import { dom } from '@core/dom/dom.ts';
import { normalizeSearchDisplayQuery } from '@core/search/searchQuery.ts';
import { createSearchBarError, normalizeOptionValues, normalizeSearchBarOptions, normalizeSearchBarValue } from '@features/controls/searchbar/guards.ts';
import { createSearchBarElements, resolveSearchBarParentElement } from '@features/controls/searchbar/dom.ts';
import { setupSearchBarEventListeners } from '@features/controls/searchbar/events.ts';
import { renderSearchBar } from '@features/controls/searchbar/view.ts';
import type { NormalizedSearchBarOptions, SearchBarOptions, SearchBarParentTarget } from '@features/controls/searchbar/types.ts';

class SearchBar {
    #elements: { container: HTMLElement; input: HTMLInputElement } | null = null;
    readonly #resources = new ResourceTracker();
    #pendingSearch: { query: string; event?: Event } | null = null;
    #eventsBound = false;

    options: NormalizedSearchBarOptions;
    searchTimeout: number | null = null;
    get initialized(): boolean {
        return this.#elements !== null;
    }

    constructor(options: SearchBarOptions = {}) {
        this.options = normalizeSearchBarOptions(options);
        normalizeOptionValues(this.options);
    }

    render(): string {
        return renderSearchBar(this.options);
    }

    initialize(parent: SearchBarParentTarget): HTMLElement {
        if (this.initialized) {
            this.destroy();
        }

        const parentElement = resolveSearchBarParentElement(parent);
        if (!parentElement) {
            const message = 'Parent element not found';
            errorHandler.error('SearchBar', message);
            throw createSearchBarError(message);
        }

        const elements = this.#createElements();
        parentElement.appendChild(elements.container);
        this.#applyElements(elements);
        return elements.container;
    }

    initializeBefore(parent: SearchBarParentTarget, beforeElement: Element): HTMLElement {
        if (this.initialized) {
            this.destroy();
        }

        const parentElement = resolveSearchBarParentElement(parent);
        if (!parentElement) {
            const message = 'Parent element not found';
            errorHandler.error('SearchBar', message);
            throw createSearchBarError(message);
        }

        const elements = this.#createElements();
        parentElement.insertBefore(elements.container, beforeElement);
        this.#applyElements(elements);
        return elements.container;
    }

    setupEventListeners(): void {
        if (this.#eventsBound || !this.initialized) return;
        this.#eventsBound = true;
        setupSearchBarEventListeners({
            getContainer: (): HTMLElement | null => this.getContainer(),
            getInput: (): HTMLInputElement | null => this.getInput(),
            scheduleSearch: (query: string, event: Event): void => this.#scheduleSearch(query, event),
            cancelPendingSearch: (): void => this.cancelPendingSearch(),
            clearQuery: (): void => {
                this.options.onClear?.();
            },
            on: (target: EventTarget, event: string, handler: (eventObject: Event) => void): (() => void) | null => {
                return this.#resources.addEventListener(target, event, handler);
            },
            clear: (triggerClear?: boolean): void => {
                this.clear(triggerClear);
            }
        });
    }

    getValue(): string {
        const input = this.#elements?.input ?? null;
        return input ? normalizeSearchDisplayQuery(input.value) : '';
    }

    setValue<T>(value: T, triggerSearch: boolean = false): void {
        const input = this.#elements?.input ?? null;
        if (!input) {
            return;
        }

        const nextValue = normalizeSearchBarValue(value);
        this.cancelPendingSearch();
        dom.setProperty(input, 'value', nextValue);

        if (triggerSearch) {
            this.#scheduleSearch(normalizeSearchDisplayQuery(nextValue));
        }
    }

    flushPendingSearch(): boolean {
        const pending = this.#pendingSearch;
        this.cancelPendingSearch();
        if (pending === null) return false;
        if (pending.event === undefined) this.options.onSearch?.(pending.query);
        else this.options.onSearch?.(pending.query, pending.event);
        return true;
    }

    cancelPendingSearch(): void {
        if (this.searchTimeout !== null) this.#resources.clearTimer(this.searchTimeout);
        this.searchTimeout = null;
        this.#pendingSearch = null;
    }

    #scheduleSearch(query: string, event?: Event): void {
        this.cancelPendingSearch();
        this.#pendingSearch = event === undefined ? { query } : { query, event };
        this.searchTimeout = this.#resources.setTimeout(() => {
            this.flushPendingSearch();
        }, this.options.debounceTime);
    }

    clear(triggerClear: boolean = true): void {
        this.cancelPendingSearch();
        const input = this.#elements?.input ?? null;
        if (!input) {
            return;
        }

        dom.setProperty(input, 'value', '');
        if (triggerClear) {
            this.options.onClear?.();
        }
    }

    setLoading(loading: boolean): void {
        const container = this.#elements?.container;
        if (container) setSearchFieldLoading(container, loading);
    }

    focus(): void {
        this.#elements?.input.focus();
    }

    blur(): void {
        this.#elements?.input.blur();
    }

    updateOptions(newOptions: Partial<SearchBarOptions>): void {
        this.options = normalizeSearchBarOptions({ ...this.options, ...newOptions });
        normalizeOptionValues(this.options);

        const elements = this.#elements;
        if (!elements) {
            return;
        }

        if (newOptions.placeholder !== undefined) {
            dom.setProperty(elements.input, 'placeholder', this.options.placeholder);
        }
        if (newOptions.width !== undefined) {
            dom.setStyle(elements.container, 'width', this.options.width);
        }
    }

    dispose(): void {
        this.destroy();
    }

    destroy(): boolean {
        const wasInitialized = this.initialized;
        this.cancelPendingSearch();

        const container = this.#elements?.container ?? null;
        if (container) {
            dom.remove(container);
        }

        this.#elements = null;
        this.#eventsBound = false;

        this.#resources.cleanup();
        return wasInitialized;
    }

    isFocused(): boolean {
        const input = this.#elements?.input ?? null;
        if (!input) {
            return false;
        }
        return getDocument().activeElement === input;
    }

    getContainer(): HTMLElement | null {
        return this.#elements?.container ?? null;
    }

    getInput(): HTMLInputElement | null {
        return this.#elements?.input ?? null;
    }

    #createElements(): { container: HTMLElement; input: HTMLInputElement } {
        try {
            return createSearchBarElements(this.options);
        } catch (error) {
            const runtimeError = error instanceof Error ? ensureError(error) : createSearchBarError('Failed to create elements');
            errorHandler.error('SearchBar', runtimeError.message);
            throw runtimeError;
        }
    }

    #applyElements(elements: { container: HTMLElement; input: HTMLInputElement }): void {
        this.#elements = elements;
        this.setupEventListeners();
    }
}

export { SearchBar };
