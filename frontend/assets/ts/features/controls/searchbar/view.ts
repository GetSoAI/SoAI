/* SoAI - Controls feature searchbar rendering [frontend/assets/ts/features/controls/searchbar/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { NormalizedSearchBarOptions } from '@features/controls/searchbar/types.ts';

const renderSearchBar = (options: NormalizedSearchBarOptions): string => {
    const containerClasses = `searchbar-container ${options.containerClass ?? ''}`.trim();
    const inputClasses = `searchbar-input ${options.inputClass ?? ''}`.trim();

    return `
                <div class="${containerClasses}" data-searchbar-id="${options.id}">
                    <input type="text"
                        id="${options.id}"
                        class="${inputClasses}"
                        placeholder="${options.placeholder}"
                        autocomplete="off">
                    ${options.showIcon ? '<span class="searchbar-icon"></span>' : ''}
                </div>
            `;
};

export { renderSearchBar };
