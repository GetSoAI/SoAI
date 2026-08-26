/* SoAI - Shared serialization JSON form [frontend/assets/ts/core/serialization/jsonForm.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { safeJsonStringify } from '@core/serialization/json.ts';

type JsonFormParseResult<TValue> = { ok: true; value: TValue } | { ok: false; error: Error };

const parseJsonFormValue = <TValue>(parser: (value: string) => TValue, value: string): JsonFormParseResult<TValue> => {
    try {
        return { ok: true, value: parser(value) };
    } catch (error) {
        const parsedError = ensureError(error);
        errorHandler.debug('Serialization', 'JSON form parse failed', parsedError);
        return { ok: false, error: parsedError };
    }
};

const formatNullableJsonFormValue = <T>(value: T): string => {
    return value === null || value === undefined ? '' : safeJsonStringify(value);
};

export { formatNullableJsonFormValue, parseJsonFormValue };
export type { JsonFormParseResult };
