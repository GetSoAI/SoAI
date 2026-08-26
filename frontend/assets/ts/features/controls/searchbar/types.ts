/* SoAI - Controls feature searchbar contracts [frontend/assets/ts/features/controls/searchbar/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface SearchBarOptions {
    placeholder?: string | undefined;
    width?: string | undefined;
    debounceTime?: number | undefined;
    alwaysExpanded?: boolean | undefined;
    id?: string | undefined;
    containerClass?: string | undefined;
    inputClass?: string | undefined;
    onSearch?: ((query: string, event?: Event) => void) | null | undefined;
    onClear?: (() => void) | null | undefined;
    showIcon?: boolean | undefined;
}

interface NormalizedSearchBarOptions {
    placeholder: string;
    width: string;
    debounceTime: number;
    alwaysExpanded: boolean;
    id: string;
    containerClass: string;
    inputClass: string;
    onSearch: ((query: string, event?: Event) => void) | null;
    onClear: (() => void) | null;
    showIcon: boolean;
}

interface SearchBarElements {
    container: HTMLElement;
    input: HTMLInputElement;
}

interface SearchBarError extends Error {
    name: 'SearchBarError';
}

type SearchBarParentTarget = Element | string;

export type { NormalizedSearchBarOptions, SearchBarElements, SearchBarError, SearchBarOptions, SearchBarParentTarget };
