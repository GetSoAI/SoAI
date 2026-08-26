/* SoAI - Authoritative power operation presentation state [frontend/assets/ts/pages/power/state/powerOperationState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PowerOperationResponse } from '@core/api/contracts/powerContracts.ts';

type PowerOperationPresentationMode = 'countdown' | 'transition' | 'completed' | 'closed';

interface PowerOperationPresentation {
    mode: PowerOperationPresentationMode;
    remainingMs: number;
    cancellable: boolean;
    notificationCode: string | null;
}

const projectPowerOperationPresentation = (operation: PowerOperationResponse, nowMs: number): PowerOperationPresentation => {
    if (operation.status === 'scheduled') {
        return {
            mode: 'countdown',
            remainingMs: Math.max(0, operation.executeAtMs - nowMs),
            cancellable: true,
            notificationCode: null
        };
    }
    if (operation.status === 'executing') {
        return { mode: 'transition', remainingMs: 0, cancellable: false, notificationCode: null };
    }
    if (operation.status === 'completed') {
        return { mode: 'completed', remainingMs: 0, cancellable: false, notificationCode: null };
    }
    return {
        mode: 'closed',
        remainingMs: 0,
        cancellable: false,
        notificationCode: operation.status === 'failed' ? (operation.errorCode ?? 'power_operation_failed') : null
    };
};

export { projectPowerOperationPresentation };
export type { PowerOperationPresentation, PowerOperationPresentationMode };
