/* SoAI - Shared frontend query tabs [frontend/assets/ts/core/queryTabs.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isObject } from '@core/typeGuards.ts';

type QueryParameters = Record<string, JsonValue | null | undefined> | null | undefined;

const resolveTabFromQuery = (parameters: QueryParameters, allowedTabs: readonly string[]): string | null => {
    if (!isArray(allowedTabs) || allowedTabs.length === 0) return null;
    if (!isObject(parameters)) return null;
    const tab = toTrimmedString(parameters['tab']);
    if (!tab) return null;
    return allowedTabs.includes(tab) ? tab : null;
};

export { resolveTabFromQuery };
