/* SoAI - Shared page controls select controller [frontend/assets/ts/core/pagecontrols/selectController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { setSelectValueAndSyncDefault } from '@core/dom/selectSelection.ts';

interface PageControlSelectState {
    requestedValue: string;
    visibleValue: string;
}

const normalizeControlValue = (value: string): string => value.trim();

const getPageControlSelectOptionValues = (select: HTMLSelectElement): string[] => Array.from(select.options, (option) => option.value);

const resolvePageControlSelectValue = (requestedValue: string, availableValues: ReadonlyArray<string>, fallbackValue: string): string => {
    const requested = normalizeControlValue(requestedValue);
    if (requested && availableValues.includes(requested)) {
        return requested;
    }
    const fallback = normalizeControlValue(fallbackValue);
    if (fallback && availableValues.includes(fallback)) {
        return fallback;
    }
    return availableValues[0] ?? fallback;
};

const syncPageControlSelectValue = (select: HTMLSelectElement, requestedValue: string, availableValues: ReadonlyArray<string>, fallbackValue: string): PageControlSelectState => {
    const visibleValue = resolvePageControlSelectValue(requestedValue, availableValues, fallbackValue);
    setSelectValueAndSyncDefault(select, visibleValue);
    return {
        requestedValue: normalizeControlValue(requestedValue),
        visibleValue
    };
};

const readPageControlSelectValue = (select: HTMLSelectElement): string => normalizeControlValue(select.value);

export { getPageControlSelectOptionValues, readPageControlSelectValue, resolvePageControlSelectValue, syncPageControlSelectValue };
export type { PageControlSelectState };
