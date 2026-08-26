/* SoAI - Main status snapshot evaluation [frontend/assets/ts/core/mainstatusmonitor/status.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SystemStatusResource } from '@core/realtime/streammanager/resourceRegistry.ts';

const resolveMainStatusUpdate = (value: SystemStatusResource, currentState: string): string | null => {
    if (value.mainState === currentState) {
        return null;
    }
    return value.mainState;
};

export { resolveMainStatusUpdate };
