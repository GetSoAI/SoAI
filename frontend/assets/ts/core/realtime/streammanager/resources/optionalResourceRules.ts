/* SoAI - Shared realtime optional resource rules [frontend/assets/ts/core/realtime/streammanager/resources/optionalResourceRules.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { HARDWARE } from '@core/realtime/streammanager/resources/ids.ts';
import type { ResourceOptionRule } from '@core/realtime/streammanager/resources/resourceState.ts';
import { isObject, isString } from '@core/typeGuards.ts';

const createOptionalResourceRules = (): Map<string, ResourceOptionRule> => {
    const extractMessage = (error: Error | JsonValue | undefined): string => {
        if (error instanceof Error) {
            return error.message;
        }
        if (!isObject(error)) {
            return '';
        }
        const messageValue = error['message'];
        if (isString(messageValue)) {
            return messageValue;
        }
        return messageValue !== undefined ? String(messageValue) : '';
    };

    return new Map([
        [
            HARDWARE,
            {
                statuses: new Set([503, 404]),
                match: (error) => /hardware manager/i.test(extractMessage(error))
            }
        ]
    ]);
};

export { createOptionalResourceRules };
