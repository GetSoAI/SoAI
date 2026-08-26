/* SoAI - Indicators feature validation [frontend/assets/ts/features/indicators/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasFunctionProperties, isObject } from '@core/typeGuards.ts';
import type { StorageInterface, TelemetryServiceInterface } from '@features/indicators/contracts.ts';

const isTelemetryService = <T>(value: T): value is T & TelemetryServiceInterface => {
    if (!isObject(value)) {
        return false;
    }

    return hasFunctionProperties(value, ['observeMetric', 'subscribe', 'publishMetric']);
};

const isStorageInterface = <T>(value: T): value is T & StorageInterface => {
    return value !== null && value !== undefined && isObject(value);
};

export { isStorageInterface, isTelemetryService };
