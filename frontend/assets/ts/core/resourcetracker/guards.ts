/* SoAI - Shared resource tracker validation [frontend/assets/ts/core/resourcetracker/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction, isObject, isString } from '@core/typeGuards.ts';
import type { EventListenerOptions, EventTargetContract, EventTargetInput } from '@core/resourcetracker/types.ts';

const toCaptureFlag = (options: EventListenerOptions | boolean): boolean => (typeof options === 'boolean' ? options : Boolean(options?.capture));

const isIterable = (value: EventTargetInput): value is Iterable<EventTargetContract> => {
    if (!value) return false;
    if (isString(value)) return false;
    return Symbol.iterator in Object(value);
};

const isEventTargetContract = (value: EventTargetInput): value is EventTargetContract => {
    if (!isObject(value)) return false;
    return 'addEventListener' in value && isFunction(value.addEventListener) && 'removeEventListener' in value && isFunction(value.removeEventListener);
};

const toTargetArray = (input: EventTargetInput): EventTargetContract[] => {
    if (!input) return [];
    if (isEventTargetContract(input)) return [input];
    if (isIterable(input)) {
        const results: EventTargetContract[] = [];
        for (const entry of input) {
            const resolved = toTargetArray(entry);
            if (resolved.length > 0) {
                results.push(...resolved);
            }
        }
        return results;
    }
    return [];
};

export { toCaptureFlag, toTargetArray };
