/* SoAI - Model detail page contract boundary parameter category metadata [frontend/assets/ts/pages/modeldetail/contracts/parameterCategoryMetadata.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isObject, isString } from '@core/typeGuards.ts';
import type { ParameterCategory } from '@pages/modeldetail/contracts/parameterTypes.ts';

const resolveParameterCategoryLabel = (category: ParameterCategory | undefined, fallback: string): string => {
    if (isString(category) && category.trim().length > 0) {
        return category;
    }
    if (isObject(category)) {
        const title = category['title'];
        if (isString(title) && title.trim().length > 0) {
            return title;
        }
    }
    return fallback;
};

export { resolveParameterCategoryLabel };
