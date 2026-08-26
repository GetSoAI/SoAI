/* SoAI - Shared realtime system status resource [frontend/assets/ts/core/realtime/streammanager/resources/systemStatusResource.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeSystemStatus } from '@core/api/contracts/systemContracts.ts';
import { observeServerTime } from '@core/time/serverTimeClock.ts';
import type { SystemStatusResource } from '@core/realtime/streammanager/resourceRegistry.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

const normalizeSystemStatusResource = (payload: JsonValue | null): SystemStatusResource => {
    const status = decodeSystemStatus(payload);
    observeServerTime(status.timestampMs);
    if (status.mainState === null) {
        throw new TypeError('System status response.main_state must be a non-empty string');
    }
    return { ...status, mainState: status.mainState };
};

export { normalizeSystemStatusResource };
