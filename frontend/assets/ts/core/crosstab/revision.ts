/* SoAI - Shared crosstab revision [frontend/assets/ts/core/crosstab/revision.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNumber, isObject, isString } from '@core/typeGuards.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

interface CrossTabRevision {
    counter: number;
    origin: string;
}

const normalizeCrossTabRevision = (value: JsonValue | undefined, fallbackOrigin: string | null = null): CrossTabRevision | null => {
    if (!isObject(value)) {
        return null;
    }
    const counterValue = value['counter'];
    const originValue = value['origin'];
    const counter = isNumber(counterValue) && Number.isFinite(counterValue) ? Math.max(0, Math.floor(counterValue)) : null;
    const origin = isString(originValue) && originValue.trim() ? originValue.trim() : fallbackOrigin?.trim() || null;
    if (counter === null || !origin) {
        return null;
    }
    return { counter, origin };
};

const compareCrossTabRevision = (left: CrossTabRevision | null, right: CrossTabRevision | null): number => {
    if (!left && !right) {
        return 0;
    }
    if (!left) {
        return -1;
    }
    if (!right) {
        return 1;
    }
    if (left.counter !== right.counter) {
        return left.counter - right.counter;
    }
    if (left.origin === right.origin) {
        return 0;
    }
    return left.origin.localeCompare(right.origin, 'en');
};

const createNextCrossTabRevision = (current: CrossTabRevision | null, origin: string): CrossTabRevision => ({
    counter: (current?.counter ?? 0) + 1,
    origin
});

const serializeCrossTabRevision = (revision: CrossTabRevision): JsonObject => ({
    counter: revision.counter,
    origin: revision.origin
});

export { compareCrossTabRevision, createNextCrossTabRevision, normalizeCrossTabRevision, serializeCrossTabRevision };
export type { CrossTabRevision };
