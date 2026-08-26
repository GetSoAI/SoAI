/* SoAI - Charts feature filter option types [frontend/assets/ts/features/charts/chartfilters/filterOptionTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';

type FilterType = 'chartType' | 'category' | 'subcategory' | 'timeRange' | 'candleInterval';

type FilterValue = string | number;

interface FilterOption {
    value: FilterValue;
    label?: string | undefined;
    [key: string]: JsonValue | undefined;
}

type FilterOptionInput = FilterOption | FilterValue;
type FilterOptionsInput = FilterOptionInput[];

type FilterIdMap = Partial<Record<FilterType, string>>;
type FilterLabelMap = Partial<Record<FilterType, string>>;

export type { FilterIdMap, FilterLabelMap, FilterOption, FilterOptionInput, FilterOptionsInput, FilterType, FilterValue };
