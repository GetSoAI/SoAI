/* SoAI - Main status snapshot evaluation [frontend/assets/ts/core/mainstatusmonitor/status.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { StreamSnapshot } from '@core/mainstatusmonitor/types.ts';
import type { SystemStatusResource } from '@core/realtime/streammanager/resourceRegistry.ts';

const resolveMainStatusUpdate = (value: SystemStatusResource, currentState: string): string | null => {
    if (value.mainState === currentState) {
        return null;
    }
    return value.mainState;
};

const UNCONFIRMED_MAIN_STATES: ReadonlySet<string> = new Set(['unknown', 'reconnecting']);

const resolveMainSnapshotState = (snapshot: StreamSnapshot | null, currentState: string): string => {
    if (snapshot?.status === 'ready' && snapshot.value) return snapshot.value.mainState;
    if (snapshot?.status === 'recovering' && snapshot.value && !UNCONFIRMED_MAIN_STATES.has(currentState)) return currentState;
    if (snapshot?.status === 'recovering' || snapshot?.status === 'disconnected') return 'reconnecting';
    return 'unknown';
};

export { resolveMainStatusUpdate, resolveMainSnapshotState };
