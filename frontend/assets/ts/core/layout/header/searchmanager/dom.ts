/* SoAI - Shared layout search manager DOM contracts [frontend/assets/ts/core/layout/header/searchmanager/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import type { SearchManagerHost, SearchManagerRefs } from '@core/layout/header/searchmanager/types.ts';

const REQUIRE_DOM_ERROR_CONTAINER = 'HeaderSearchManager requires container to be initialized';
const REQUIRE_DOM_ERROR_INPUT = 'HeaderSearchManager requires input to be initialized';
const REQUIRE_DOM_ERROR_BUTTON = 'HeaderSearchManager requires button to be initialized';
const REQUIRE_DOM_ERROR_DROPDOWN = 'HeaderSearchManager requires dropdown to be initialized';
const REQUIRE_DROPDOWN_ITEMS_ERROR = 'HeaderSearchManager expected search item to be an HTMLElement';
const MISSING_INITIAL_CONTAINER = 'Header search markup is incomplete: missing search container';
const MISSING_INITIAL_INPUT = 'Header search markup is incomplete: missing search input';
const MISSING_INITIAL_BUTTON = 'Header search markup is incomplete: missing search button';
const MISSING_INITIAL_DROPDOWN = 'Header search markup is incomplete: missing search dropdown';

const requireSearchDom = (host: SearchManagerHost): SearchManagerRefs => {
    const container = host.getDom('searchContainer');
    const input = host.getDom('searchInput');
    const button = host.getDom('searchButton');
    const dropdown = host.getDom('searchDropdown');
    if (!(container instanceof HTMLElement)) {
        throw new Error(REQUIRE_DOM_ERROR_CONTAINER);
    }
    if (!(input instanceof HTMLInputElement)) {
        throw new Error(REQUIRE_DOM_ERROR_INPUT);
    }
    if (!(button instanceof HTMLElement)) {
        throw new Error(REQUIRE_DOM_ERROR_BUTTON);
    }
    if (!(dropdown instanceof HTMLElement)) {
        throw new Error(REQUIRE_DOM_ERROR_DROPDOWN);
    }
    return { container, input, button, dropdown };
};

const resolveSearchDom = (host: SearchManagerHost): SearchManagerRefs => {
    const container = host.getDom('searchContainer');
    const input = host.getDom('searchInput');
    const button = host.getDom('searchButton');
    const dropdown = host.getDom('searchDropdown');

    if (!(container instanceof HTMLElement)) {
        throw new Error(MISSING_INITIAL_CONTAINER);
    }
    if (!(input instanceof HTMLInputElement)) {
        throw new Error(MISSING_INITIAL_INPUT);
    }
    if (!(button instanceof HTMLElement)) {
        throw new Error(MISSING_INITIAL_BUTTON);
    }
    if (!(dropdown instanceof HTMLElement)) {
        throw new Error(MISSING_INITIAL_DROPDOWN);
    }
    return { container, input, button, dropdown };
};

const collectSearchItems = (dropdown: HTMLElement): HTMLElement[] => {
    const elements = dom.resolveAll('.search-item', dropdown);
    const items: HTMLElement[] = [];
    for (const element of elements) {
        if (!(element instanceof HTMLElement)) {
            throw new Error(REQUIRE_DROPDOWN_ITEMS_ERROR);
        }
        items.push(element);
    }
    return items;
};

export { collectSearchItems, requireSearchDom, resolveSearchDom };
