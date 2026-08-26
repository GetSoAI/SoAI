/* SoAI - Dashboard page contract boundary status manager [frontend/assets/ts/pages/dashboard/contracts/statusManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { hasFunctionProperties, isObject } from '@core/typeGuards.ts';

interface StatusManagerContract {
    getDescription(status: string): string;
    getCollectionBadgeClass(status: string): string;
    normalizeStatus(status: JsonValue): string;
}

const isStatusManagerContract = <T>(value: T | JsonValue | null | undefined): value is T & StatusManagerContract => {
    if (!isObject(value)) {
        return false;
    }
    return hasFunctionProperties(value, ['getDescription', 'getCollectionBadgeClass', 'normalizeStatus']);
};

export { isStatusManagerContract };
export type { StatusManagerContract };
