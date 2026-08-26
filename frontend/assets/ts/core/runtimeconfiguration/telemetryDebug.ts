/* SoAI - Shared runtime configuration telemetry debug [frontend/assets/ts/core/runtimeconfiguration/telemetryDebug.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getGlobalScope } from '@core/environment/public.ts';
import { readStorageJson } from '@core/storage/ttlStorageCache.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isBoolean, isString } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface LocationLike {
    search: string;
}

const interpretBooleanFlag = (value: JsonValue | null | undefined): boolean | null => {
    if (isBoolean(value)) {
        return value;
    }
    if (isString(value)) {
        const normalized = value.trim().toLowerCase();
        if (normalized === '1' || normalized === 'true' || normalized === 'yes' || normalized === 'on') {
            return true;
        }
        if (normalized === '0' || normalized === 'false' || normalized === 'no' || normalized === 'off') {
            return false;
        }
    }
    return null;
};

const resolveTelemetryDebugFlag = (location: LocationLike): boolean => {
    try {
        const parameters = new URLSearchParams(location.search);
        const explicit = parameters.get('telemetry');
        if (explicit) {
            const normalized = explicit.trim().toLowerCase();
            if (normalized === 'debug') {
                return true;
            }
            if (normalized === 'info') {
                return false;
            }
        }
        const debugParameter = parameters.get('soaiTelemetryDebug');
        const interpreted = interpretBooleanFlag(debugParameter);
        if (interpreted !== null) {
            return interpreted;
        }
    } catch (error) {
        ensureError(error);
        getGlobalScope()?.console?.error?.('RuntimeConfiguration: reading query parameters failed', error);
    }
    const scope = getGlobalScope();
    if (!scope) {
        return false;
    }
    try {
        const stored = readStorageJson('localStorage', 'soai.telemetry.debug');
        const interpreted = interpretBooleanFlag(stored);
        if (interpreted !== null) {
            return interpreted;
        }
    } catch (error) {
        ensureError(error);
        scope.console?.warn?.('RuntimeConfiguration: telemetry debug storage access failed', error);
    }
    return false;
};

export { resolveTelemetryDebugFlag };
