/* SoAI - Shared API retry after header [frontend/assets/ts/core/api/retryAfterHeader.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { serverEpochMs } from '@core/time/clock.ts';

const parseRetryAfterHeaderSeconds = (value: string | null): number | null => {
    if (!value) {
        return null;
    }
    const trimmed = value.trim();
    if (!trimmed) {
        return null;
    }
    const numeric = Number(trimmed);
    if (Number.isFinite(numeric) && numeric > 0) {
        return numeric;
    }
    const retryAtMs = new Date(trimmed).getTime();
    if (!Number.isFinite(retryAtMs)) {
        return null;
    }
    const seconds = Math.ceil((retryAtMs - serverEpochMs()) / 1000);
    return seconds > 0 ? seconds : null;
};

export { parseRetryAfterHeaderSeconds };
