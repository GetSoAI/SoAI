/* SoAI - Shared storage sync snapshot [frontend/assets/ts/core/storage/service/syncSnapshot.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAnimationSpeed } from '@core/animations/speed.ts';
import { isDateFormatPreference, isMeasurementUnitsPreference, isRegionalLocalePreference } from '@core/localization/public.ts';
import { isInterfaceScalePercent } from '@core/layout/interfaceScale.ts';
import { normalizeSessionData } from '@core/storage/normalization.ts';
import { isBoolean, isObject, isString } from '@core/typeGuards.ts';
import { normalizeCrossTabRevision, serializeCrossTabRevision, type CrossTabRevision } from '@core/crosstab/revision.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

interface StorageSyncSnapshot {
    origin: string;
    revision: CrossTabRevision;
    cache: JsonObject;
    session: JsonObject;
    redirectAfterLogin: string | null;
    isAuthenticated: boolean;
}

const serializeStorageSyncSnapshot = (snapshot: StorageSyncSnapshot): JsonObject => ({
    origin: snapshot.origin,
    revision: serializeCrossTabRevision(snapshot.revision),
    cache: snapshot.cache,
    session: snapshot.session,
    'redirect_after_login': snapshot.redirectAfterLogin,
    'is_authenticated': snapshot.isAuthenticated
});

const normalizeStorageSyncSnapshot = (value: JsonValue | undefined): StorageSyncSnapshot | null => {
    if (!isObject(value)) {
        return null;
    }
    const origin = value['origin'];
    const revisionValue = value['revision'];
    const cache = value['cache'];
    const session = value['session'];
    const redirectAfterLogin = value['redirect_after_login'];
    const isAuthenticated = value['is_authenticated'];

    if (!isString(origin) || !origin.trim()) {
        return null;
    }
    const normalizedOrigin = origin.trim();
    const revision = normalizeCrossTabRevision(revisionValue, normalizedOrigin);
    if (!revision) {
        return null;
    }
    if (!isJsonObject(cache)) {
        return null;
    }
    const uiCache = cache['ui'];
    if (isObject(uiCache)) {
        const animationSpeed = uiCache['animation_speed'];
        if (animationSpeed !== undefined && !isAnimationSpeed(animationSpeed)) {
            return null;
        }
        const interfaceScale = uiCache['interface_scale'];
        if (interfaceScale !== undefined && !isInterfaceScalePercent(interfaceScale)) {
            return null;
        }
        const regionalLocale = uiCache['regional_locale'];
        if (regionalLocale !== undefined && !isRegionalLocalePreference(regionalLocale)) {
            return null;
        }
        const dateFormat = uiCache['date_format'];
        if (dateFormat !== undefined && !isDateFormatPreference(dateFormat)) {
            return null;
        }
        const measurementUnits = uiCache['measurement_units'];
        if (measurementUnits !== undefined && !isMeasurementUnitsPreference(measurementUnits)) {
            return null;
        }
        const headerClockEnabled = uiCache['header_clock_enabled'];
        if (headerClockEnabled !== undefined && !isBoolean(headerClockEnabled)) {
            return null;
        }
        const clockSecondsEnabled = uiCache['clock_seconds_enabled'];
        if (clockSecondsEnabled !== undefined && !isBoolean(clockSecondsEnabled)) {
            return null;
        }
    }
    if (redirectAfterLogin !== null && redirectAfterLogin !== undefined && !isString(redirectAfterLogin)) {
        return null;
    }
    if (!isBoolean(isAuthenticated)) {
        return null;
    }

    return {
        origin: normalizedOrigin,
        revision,
        cache,
        session: normalizeSessionData(session),
        redirectAfterLogin: redirectAfterLogin === undefined ? null : redirectAfterLogin,
        isAuthenticated
    };
};

export { normalizeStorageSyncSnapshot, serializeStorageSyncSnapshot };
export type { StorageSyncSnapshot };
