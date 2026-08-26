/* SoAI - Shared UI dialogs validation [frontend/assets/ts/core/ui/modals/dialogs/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { sanitizeForId } from '@core/identifiers.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { hasFunctionProperty, isObject, isString } from '@core/typeGuards.ts';
import type { ClipboardServiceInterface } from '@core/ui/modals/dialogs/types.ts';

const isClipboardService = <T>(value: T): value is T & ClipboardServiceInterface => {
    if (!isObject(value)) {
        return false;
    }

    return hasFunctionProperty(value, 'isSupported') && hasFunctionProperty(value, 'copyText');
};

const normalizeDomToken = (value: JsonValue, label: string): string => {
    if (!isString(label) || !label.trim()) {
        throw new Error('normalizeDomToken requires a label');
    }

    const source = toTrimmedString(value);
    if (!source) {
        throw new Error(`${label} requires a non-empty value`);
    }

    try {
        return sanitizeForId(source.replace(/_/g, '-'));
    } catch (_error) {
        throw new Error(`${label} requires a non-empty value`);
    }
};

export { isClipboardService, normalizeDomToken };
