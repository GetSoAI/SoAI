/* SoAI - Search page events [frontend/assets/ts/pages/search/controllers/page/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';

const resolveSearchQueryFromParameters = (parameters: JsonObject | null, normalizeQuery: (value: string | null) => string): string => {
    const query = parameters?.['q'];
    return normalizeQuery(typeof query === 'string' ? query : null);
};
export { resolveSearchQueryFromParameters };
