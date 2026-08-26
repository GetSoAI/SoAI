/* SoAI - Overlays feature restart contracts [frontend/assets/ts/features/overlays/restart/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SystemHealthResponse, SystemStatusResponse } from '@core/api/contracts/systemContracts.ts';
import type { RequestOptions } from '@core/api/types/request.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';

interface RestartContent {
    message: string;
    description: string;
    statusIcon: IconName;
}

type PersistentRestartOperationType = 'restart-application' | 'system-reboot' | 'system-shutdown' | 'system-sleep' | 'update-soai' | 'restore-backup';
type OperationType = PersistentRestartOperationType | 'connection-lost';

interface RestartOperationState {
    type: PersistentRestartOperationType;
    timestamp: number;
    retry: number;
    observeTransition: boolean;
    interruptionObserved: boolean;
}

interface RestartOverlayShowOptions {
    observeTransition?: boolean;
}

interface RestartSessionRepository {
    save: (state: RestartOperationState) => void;
    read: () => RestartOperationState | null;
    clear: () => void;
}

interface RestartSessionStorage {
    getItem: (key: string) => string | null;
    setItem: (key: string, value: string) => void;
    removeItem: (key: string) => void;
}

interface ApiInterface {
    system: {
        health: (options?: RequestOptions) => Promise<SystemHealthResponse>;
        status: () => Promise<SystemStatusResponse>;
    };
    initialize: () => Promise<void | string>;
}

interface DomInterface {
    querySafe: (selector: string) => HTMLElement | null;
}

interface OverlayElements {
    overlay: HTMLElement | null;
    message: HTMLElement | null;
    description: HTMLElement | null;
    statusIcon: HTMLElement | null;
}

interface LocationInterface {
    reload: () => void;
}

export type { ApiInterface, DomInterface, LocationInterface, OperationType, OverlayElements, PersistentRestartOperationType, RestartContent, RestartOperationState, RestartOverlayShowOptions, RestartSessionRepository, RestartSessionStorage };
