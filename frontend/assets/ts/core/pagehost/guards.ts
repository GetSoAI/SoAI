/* SoAI - Shared pagehost validation [frontend/assets/ts/core/pagehost/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction, isObject } from '@core/typeGuards.ts';
import type { PageRegistry } from '@core/pagehost/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

const isPageRegistry = (value: PageRegistry | JsonValue | null | undefined): value is PageRegistry => {
    if (!isObject(value)) {
        return false;
    }
    return 'create' in value && isFunction(value.create) && 'getMeta' in value && isFunction(value.getMeta);
};

export { isPageRegistry };
