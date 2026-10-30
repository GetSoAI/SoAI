/* SoAI - Controls feature searchbar events [frontend/assets/ts/features/controls/searchbar/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { normalizeSearchDisplayQuery } from '@core/search/searchQuery.ts';
interface SearchBarEventsHost {
    getContainer: () => HTMLElement | null;
    getInput: () => HTMLInputElement | null;
    scheduleSearch: (query: string, event: Event) => void;
    cancelPendingSearch: () => void;
    clearQuery: () => void;
    on: (target: EventTarget, event: string, handler: (eventObject: Event) => void) => (() => void) | null;
    clear: (triggerClear?: boolean) => void;
}

const setupSearchBarEventListeners = (host: SearchBarEventsHost): void => {
    const input = host.getInput();
    if (!input) {
        return;
    }

    let composing = false;
    const scheduleInput = (eventObject: Event): void => {
        host.cancelPendingSearch();
        if (composing || (eventObject instanceof InputEvent && eventObject.isComposing)) return;
        const query = normalizeSearchDisplayQuery(input.value);
        if (query.length === 0) {
            host.clearQuery();
            return;
        }
        host.scheduleSearch(query, eventObject);
    };
    host.on(input, 'input', scheduleInput);
    host.on(input, 'compositionstart', () => {
        composing = true;
        host.cancelPendingSearch();
    });
    host.on(input, 'compositionend', (eventObject: Event) => {
        composing = false;
        scheduleInput(eventObject);
    });

    host.on(input, 'keydown', (eventObject: Event) => {
        if (!(eventObject instanceof KeyboardEvent)) {
            return;
        }
        if (eventObject.key === 'Escape' && !composing && !eventObject.isComposing) {
            host.clear();
            input.blur();
        }
    });

    host.on(input, 'focus', () => {
        const container = host.getContainer();
        if (container) {
            dom.addClass(container, 'is-focused');
        }
    });

    host.on(input, 'blur', () => {
        const container = host.getContainer();
        if (container) {
            dom.removeClass(container, 'is-focused');
        }
    });
};

export { setupSearchBarEventListeners };
