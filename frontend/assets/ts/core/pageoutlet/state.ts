/* SoAI - Shared page outlet state [frontend/assets/ts/core/pageoutlet/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { formatCompactMillisecondsAsSecondsUnit } from '@core/primitives/duration.ts';
import { isFiniteNumber, isObject, isString } from '@core/typeGuards.ts';
import { PAGE_OUTLET_TIMEOUT_ERROR_NAME } from '@core/pageoutlet/constants.ts';
import type { TimeoutError } from '@core/pageoutlet/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

class PageOutletTimeoutError extends Error {
    stage: string;
    component: string;
    timeoutMs: number;

    constructor(description: string, component: string, stage: string, timeoutMs: number) {
        super(description);
        this.name = PAGE_OUTLET_TIMEOUT_ERROR_NAME;
        this.component = component;
        this.stage = stage;
        this.timeoutMs = timeoutMs;
    }
}

const isTimeoutError = (value: Error | JsonValue | null): value is PageOutletTimeoutError => {
    if (!(value instanceof PageOutletTimeoutError) || !isObject(value)) {
        return false;
    }
    return isString(value.stage) && isString(value.component) && isFiniteNumber(value.timeoutMs) && isString(value.message);
};

const resolveDocument = (element: Element | null): Document => {
    const ownerDocument = element?.ownerDocument || dom.getDocument();
    if (!ownerDocument) {
        throw new Error('PageOutlet requires a DOM document');
    }
    return ownerDocument;
};

const createTimeoutError = (component: string, stage: string, timeoutMs: number): TimeoutError => {
    return new PageOutletTimeoutError(`Page ${component} did not become ready within ${formatCompactMillisecondsAsSecondsUnit(timeoutMs)}.`, component, stage, timeoutMs);
};

export { PageOutletTimeoutError, createTimeoutError, isTimeoutError, resolveDocument };
