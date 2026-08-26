/* SoAI - Hardware feature history identity [frontend/assets/ts/features/hardware/historyIdentity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNullOrUndefined } from '@core/typeGuards.ts';

const normalizeHistoryComponent = (component: string | null | undefined): string => String(component ?? '').toLowerCase();

const normalizeIdentifier = (component: string | null | undefined, identifier: string | null | undefined): string | null => {
    if (isNullOrUndefined(identifier)) {
        return null;
    }
    const value = String(identifier).trim();
    const normalizedComponent = normalizeHistoryComponent(component);
    if (normalizedComponent === 'network') {
        return value.toLowerCase();
    }
    if (normalizedComponent === 'gpu') {
        const numeric = Number(value);
        if (Number.isFinite(numeric)) {
            return String(Math.max(0, Math.floor(numeric)));
        }
        return '0';
    }
    return value;
};

export { normalizeHistoryComponent, normalizeIdentifier };
