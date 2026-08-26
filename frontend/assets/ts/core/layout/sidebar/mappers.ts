/* SoAI - Shared frontend layout sidebar mapping [frontend/assets/ts/core/layout/sidebar/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SystemInfo } from '@core/connectionstatus/public.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { isNumber, isString } from '@core/typeGuards.ts';

const normalizeSidebarVersionValue = (version: JsonValue | undefined): string => {
    if (isString(version)) {
        return version.trim();
    }
    if (isNumber(version) && Number.isFinite(version)) {
        return String(version);
    }
    return '';
};

const extractSidebarVersionFromSystemInfo = (systemInfo: SystemInfo | JsonObject | null): string | null => {
    if (!systemInfo) {
        return null;
    }
    const soaiVersion = normalizeSidebarVersionValue(systemInfo['soaiVersion']);
    return soaiVersion || null;
};

export { extractSidebarVersionFromSystemInfo, normalizeSidebarVersionValue };
