/* SoAI - Model detail page rendering layer icon options [frontend/assets/ts/pages/modeldetail/rendering/modelDetailIconOptions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isBoolean, isNumber, isString } from '@core/typeGuards.ts';
import { isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';

function toModelDetailIconOptions(options?: JsonValue | null | undefined): IconOptions | undefined {
    if (!isJsonObject(options)) return undefined;

    const result: IconOptions = {};

    const sizeValue = options['size'];
    if (isNumber(sizeValue)) result.size = sizeValue;

    const widthValue = options['width'];
    if (isNumber(widthValue)) result.width = widthValue;

    const heightValue = options['height'];
    if (isNumber(heightValue)) result.height = heightValue;

    const strokeWidthValue = options['strokeWidth'];
    if (isNumber(strokeWidthValue)) result.strokeWidth = strokeWidthValue;

    const fillValue = options['fill'];
    if (isString(fillValue)) result.fill = fillValue;

    const strokeValue = options['stroke'];
    if (isString(strokeValue)) result.stroke = strokeValue;

    const classNameValue = options['className'];
    if (isString(classNameValue)) result.className = classNameValue;

    const attributesValue = options['attributes'];
    if (isJsonObject(attributesValue)) {
        const attrs: Record<string, string | number | boolean> = {};
        for (const [key, value] of Object.entries(attributesValue)) {
            if (!key) continue;
            if (isString(value) || isNumber(value) || isBoolean(value)) {
                attrs[key] = value;
            }
        }
        if (Object.keys(attrs).length > 0) {
            result.attributes = attrs;
        }
    }

    return result;
}

export { toModelDetailIconOptions };
