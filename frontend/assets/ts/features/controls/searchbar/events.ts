/* SoAI - Controls feature searchbar events [frontend/assets/ts/features/controls/searchbar/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { normalizeSearchDisplayQuery } from '@core/search/searchQuery.ts';
import type { NormalizedSearchBarOptions } from '@features/controls/searchbar/types.ts';

interface SearchBarEventsHost {
    options: NormalizedSearchBarOptions;
    getContainer: () => HTMLElement | null;
    getInput: () => HTMLInputElement | null;
    clearTimer: (timerId: number | null) => void;
    setTimer: (callback: () => void, delayMs: number) => number | null;
    on: (target: EventTarget, event: string, handler: (eventObject: Event) => void) => (() => void) | null;
    clear: (triggerClear?: boolean) => void;
    setSearchTimeout: (timerId: number | null) => void;
    getSearchTimeout: () => number | null;
}

const setupSearchBarEventListeners = (host: SearchBarEventsHost): void => {
    const input = host.getInput();
    if (!input) {
        return;
    }

    host.on(input, 'input', (eventObject: Event) => {
        host.clearTimer(host.getSearchTimeout());

        const query = normalizeSearchDisplayQuery(input.value);
        if (query.length === 0) {
            host.options.onClear?.();
            return;
        }

        host.setSearchTimeout(
            host.setTimer(() => {
                host.options.onSearch?.(query, eventObject);
            }, host.options.debounceTime)
        );
    });

    host.on(input, 'keydown', (eventObject: Event) => {
        if (!(eventObject instanceof KeyboardEvent)) {
            return;
        }
        if (eventObject.key === 'Escape') {
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
