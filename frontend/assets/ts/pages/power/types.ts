/* SoAI - Power page contracts [frontend/assets/ts/pages/power/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AcceptedPowerActionResponse, PowerOperationResponse } from '@core/api/contracts/powerContracts.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { CountdownOverlay, OperationType, RestartOverlayShowOptions } from '@features/overlays/public.ts';
import type { PowerActionId } from '@features/power/public.ts';

export type PowerRestartType = 'application' | 'system';

export interface PowerUi {
    root: HTMLElement;
    grid: HTMLElement;
    applicationRestartNotice: HTMLElement | null;
    applicationRestartOptions: HTMLElement | null;
    systemRestartNotice: HTMLElement | null;
    systemRestartOptions: HTMLElement | null;
}

export interface RestartOverlayService {
    show(value: OperationType, options?: RestartOverlayShowOptions): void;
    hide(): void;
}

export interface PowerOverlayService {
    show(value: string): void;
    hide(): void;
}

export interface PowerPageDependencies {
    countdownOverlay: CountdownOverlay;
    restartOverlay: RestartOverlayService;
    powerOverlay: PowerOverlayService;
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
    tone: string;
    buttonLabel: string;
    buttonVariant: string;
    options?: ReadonlyArray<{
        type: 'checkbox' | 'number';
        parameter: keyof ActionParameters;
        label: string;
        defaultValue?: number | boolean;
        min?: number;
        max?: number;
        step?: number;
    }>;
    confirm?: {
        variant: string;
        title?: string;
        warning?: string;
        message?: string;
        getMessage?: (parameters: ActionParameters) => string;
    };
    run: (parameters: ActionParameters) => Promise<PowerActionResponse>;
    successNotification: null | ((parameters: ActionParameters) => { message: string; type: string } | null);
    errorToastMessage: string | null;
    onSuccess: ((parameters: ActionParameters, result: PowerActionResponse) => void) | null;
}

export interface PowerActionEffects {
    operationAccepted(response: AcceptedPowerActionResponse): void;
}

export interface ActionParameters {
    force?: boolean;
    delay?: number;
}

export interface RestartNotification {
    reason: string;
    path: string | null;
}

export interface NormalizedRestartState {
    required: boolean;
    reasons: string[];
    notifications: RestartNotification[];
}

export interface ConfirmActionOptions {
    title?: string | undefined;
    message?: string | undefined;
    warning?: string | undefined;
    confirmText?: string | undefined;
    cancelText?: string | undefined;
    icon?: IconName | undefined;
    run?: (() => Promise<PowerActionResponse>) | undefined;
    successMessage?: string | undefined;
    errorToastMessage?: string | undefined;
    onSuccess?: ((result: PowerActionResponse) => void) | undefined;
    onError?: ((error: Error) => void) | undefined;
    variant?: string | undefined;
}
