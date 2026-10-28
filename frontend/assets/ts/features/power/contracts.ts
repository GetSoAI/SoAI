/* SoAI - Power mode contracts [frontend/assets/ts/features/power/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AcceptedPowerActionResponse, PowerOperationResponse } from '@core/api/contracts/powerContracts.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { PowerActionId } from '@features/power/actions.ts';

export interface CountdownPresentation {
    show(options: { title?: string; seconds?: number; executeAtMs?: number; prefixText?: string; suffixText?: string; cancelLabel?: string; onCancel?: () => boolean | Promise<boolean>; onComplete?: () => void }): void;
    hide(options?: { canceled?: boolean }): void;
}

export interface RestartOverlayService {
    show(value: 'restart-application' | 'system-reboot', options?: { observeTransition?: boolean }): void;
    hide(): void;
}

export interface PowerOverlayService {
    show(value: string): void;
    hide(): void;
}

export interface PowerApiShutdown {
    (options: { force?: boolean; delay?: number }): Promise<AcceptedPowerActionResponse>;
}

export interface PowerApiReboot {
    (options: { force?: boolean; delay?: number }): Promise<AcceptedPowerActionResponse>;
}

export interface PowerApi {
    restartApplication(options?: { delay?: number }): Promise<AcceptedPowerActionResponse>;
    shutdownApplication(options?: { delay?: number }): Promise<AcceptedPowerActionResponse>;
    shutdown: PowerApiShutdown;
    reboot: PowerApiReboot;
    suspend: PowerApiShutdown;
    hibernate: PowerApiShutdown;
    active(): Promise<PowerOperationResponse | null>;
    get(operationId: string): Promise<PowerOperationResponse>;
    cancel(operationId: string): Promise<PowerOperationResponse>;
}

export type PowerActionResponse = AcceptedPowerActionResponse;

export interface ActionDefinition {
    key: PowerActionId;
    title: string;
    description: string;
    icon: IconName;
    buttonLabel: string;
    variant: 'warning' | 'danger' | 'primary';
    options: ReadonlyArray<{
        type: 'checkbox' | 'number';
        parameter: keyof ActionParameters;
        label: string;
        defaultValue?: number | boolean;
        min?: number;
        max?: number;
        step?: number;
    }>;
    confirm: {
        title: string;
        message: string;
        warning: string;
        icon: IconName;
    };
}

export interface PowerActionEffects {
    operationAccepted(response: AcceptedPowerActionResponse): void;
}

export interface ActionParameters {
    force?: boolean;
    delay?: number;
}
