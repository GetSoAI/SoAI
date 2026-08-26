/* SoAI - Controls feature searchbar validation [frontend/assets/ts/features/controls/searchbar/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { generateSecureId } from '@core/primitives/idGenerator.ts';
import { isNullOrUndefined, isString } from '@core/typeGuards.ts';
import type { NormalizedSearchBarOptions, SearchBarError, SearchBarOptions } from '@features/controls/searchbar/types.ts';

class SearchBarErrorImpl extends Error implements SearchBarError {
    declare readonly name: 'SearchBarError';

    constructor(message: string) {
        super(`SearchBar: ${message}`);
        this.name = 'SearchBarError';
    }
}

const createSearchBarError = (message: string): SearchBarError => new SearchBarErrorImpl(message);

const normalizeSearchBarOptions = (options: SearchBarOptions): NormalizedSearchBarOptions => {
    const rawPlaceholder = options.placeholder;
    const placeholder = isString(rawPlaceholder) ? rawPlaceholder : isNullOrUndefined(rawPlaceholder) ? '' : String(rawPlaceholder);

    const rawWidth = options.width;
    const width = isString(rawWidth) ? rawWidth : isNullOrUndefined(rawWidth) ? '100%' : String(rawWidth);

    const rawDebounceTime = options.debounceTime;
    const debounceTime = typeof rawDebounceTime === 'number' && Number.isFinite(rawDebounceTime) && rawDebounceTime >= 0 ? Math.floor(rawDebounceTime) : 300;

    const alwaysExpanded = options.alwaysExpanded !== false;

    const rawId = options.id;
    const idCandidate = isString(rawId) ? rawId.trim() : '';
    const id = idCandidate ? idCandidate : generateSecureId({ prefix: 'searchbar', separator: '-' });

    const containerClass = isString(options.containerClass) ? options.containerClass : '';
    const inputClass = isString(options.inputClass) ? options.inputClass : '';

    const onSearch = typeof options.onSearch === 'function' ? options.onSearch : null;
    const onClear = typeof options.onClear === 'function' ? options.onClear : null;
    const showIcon = options.showIcon !== false;

    return {
        placeholder,
        width,
        debounceTime,
        alwaysExpanded,
        id,
        containerClass,
        inputClass,
        onSearch,
        onClear,
        showIcon
    };
};

const normalizeOptionValues = (options: NormalizedSearchBarOptions): void => {
    const placeholderValue = options.placeholder;
    const normalizedPlaceholder = isString(placeholderValue) ? placeholderValue : isNullOrUndefined(placeholderValue) ? '' : String(placeholderValue);
    const finalPlaceholder = normalizedPlaceholder.trim();
    if (!finalPlaceholder) {
        throw createSearchBarError('placeholder is required');
    }
    options.placeholder = finalPlaceholder;

    const widthValue = options.width;
    const normalizedWidth = isString(widthValue) ? widthValue : isNullOrUndefined(widthValue) ? '' : String(widthValue);
    options.width = normalizedWidth.trim().length ? normalizedWidth : '100%';
};

const normalizeSearchBarValue = <T>(value: T): string => {
    if (typeof value === 'string') {
        return value;
    }
    if (value === null || value === undefined) {
        return '';
    }
    return String(value);
};

export { createSearchBarError, normalizeOptionValues, normalizeSearchBarOptions, normalizeSearchBarValue };
