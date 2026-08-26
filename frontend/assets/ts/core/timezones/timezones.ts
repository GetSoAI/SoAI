/* SoAI - Shared timezone definitions [frontend/assets/ts/core/timezones/timezones.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isString } from '@core/typeGuards.ts';
import { getLanguageService } from '@core/languageservice/service.ts';

const resolveBrowserTimezone = (): string => {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (!isString(tz) || !tz.trim()) {
        throw new Error('Browser timezone could not be resolved');
    }
    return tz.trim();
};

const listSupportedTimezones = (): string[] => {
    const zones = Intl.supportedValuesOf('timeZone');
    if (!isArray(zones) || !zones.every((zone) => isString(zone) && Boolean(zone.trim()))) {
        throw new Error('Browser did not return a valid time zone list');
    }
    const normalized = zones.map((zone) => zone.trim());
    normalized.sort((firstValue, secondValue) => firstValue.localeCompare(secondValue, getLanguageService().getLocale()));
    return normalized;
};

export { listSupportedTimezones, resolveBrowserTimezone };
