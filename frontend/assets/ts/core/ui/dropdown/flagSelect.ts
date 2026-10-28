/* SoAI - Native select country flag presentation [frontend/assets/ts/core/ui/dropdown/flagSelect.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { flagAssetUrl, isFlagCountryCode } from '@core/countryFlags.ts';
import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { renderDropdownSelectControl } from '@core/ui/dropdown/selectControl.ts';

const failedAssets = new Set<string>();
const selectionRevisions = new WeakMap<HTMLSelectElement, number>();

const renderFlagSelectControl = (selectMarkup: string): string =>
    renderDropdownSelectControl({
        selectMarkup,
        shellClassName: 'dropdown-select--flag',
        prefixMarkup: '<img class="dropdown-select__flag" alt="" aria-hidden="true" width="24" height="18" hidden>'
    });

const syncFlagSelect = (select: HTMLSelectElement): void => {
    const image = dom.resolve('.dropdown-select__flag', select.parentElement);
    if (!(image instanceof HTMLImageElement)) throw new Error('Flag select image is missing.');
    const revision = (selectionRevisions.get(select) ?? 0) + 1;
    selectionRevisions.set(select, revision);
    image.hidden = true;
    image.removeAttribute('src');
    const countryCode = select.selectedOptions.item(0)?.dataset['countryCode'];
    if (!countryCode || !isFlagCountryCode(countryCode)) return;
    const path = flagAssetUrl(countryCode);
    const preload = new Image();
    preload.onload = (): void => {
        if (selectionRevisions.get(select) !== revision) return;
        failedAssets.delete(countryCode);
        image.src = path;
        image.hidden = false;
    };
    preload.onerror = (): void => {
        if (selectionRevisions.get(select) !== revision) return;
        image.hidden = true;
        if (failedAssets.has(countryCode)) return;
        failedAssets.add(countryCode);
        errorHandler.warn('CountryFlags', 'Country flag asset failed to load', { countryCode });
    };
    preload.src = path;
};

export { renderFlagSelectControl, syncFlagSelect };
