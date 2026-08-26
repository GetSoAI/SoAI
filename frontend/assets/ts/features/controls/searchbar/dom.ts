/* SoAI - Controls feature searchbar DOM contracts [frontend/assets/ts/features/controls/searchbar/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { narrowInput } from '@core/dom/narrowElement.ts';
import { isElementNode, isString } from '@core/typeGuards.ts';
import type { NormalizedSearchBarOptions, SearchBarElements, SearchBarParentTarget } from '@features/controls/searchbar/types.ts';

const resolveSearchBarParentElement = (target: SearchBarParentTarget): Element | null => {
    if (isElementNode(target)) {
        return target;
    }
    if (isString(target)) {
        return dom.resolve(target);
    }
    return null;
};

const createSearchBarElements = (options: NormalizedSearchBarOptions): SearchBarElements => {
    const containerClasses = `searchbar-container ${options.containerClass ?? ''}`.trim();
    const inputClasses = `searchbar-input ${options.inputClass ?? ''}`.trim();

    const container = dom.create('div', {
        className: containerClasses,
        dataset: { searchbarId: options.id },
        includeIdClass: false
    });
    const input = dom.create('input', {
        type: 'text',
        id: options.id,
        className: inputClasses,
        placeholder: options.placeholder,
        autocomplete: 'off',
        includeIdClass: false
    });

    const inputElement = narrowInput(input, 'Search input element');

    container.appendChild(inputElement);
    if (options.showIcon) {
        container.appendChild(dom.create('span', { className: 'searchbar-icon', includeIdClass: false }));
    }

    dom.setStyle(container, 'width', options.width);
    return { container, input: inputElement };
};

export { createSearchBarElements, resolveSearchBarParentElement };
