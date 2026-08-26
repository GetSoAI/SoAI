/* SoAI - Trusted product settings contribution contracts [frontend/assets/ts/core/edition/settingsContribution.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OsEndpoints } from '@core/api/endpoints/osEndpointContracts.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { WebuiUser } from '@core/api/contracts/webuiUserContracts.ts';
import type { NormalTabDefinition, SettingsCapabilityAvailability } from '@core/settings/contracts.ts';
import type { TaskListResponse, TaskResponse } from '@core/api/contracts/taskContracts.ts';
import type { DomEventHost, DomMutationHost, DomQueryHost, ExecutionHost, NotificationHost } from '@core/ui/controllerHosts.ts';

interface SettingsProductManager {
    render(): TrustedHtml;
    setupEventListeners(): void;
    reload(): Promise<boolean>;
    dispose(): void;
}

interface SettingsProductManagerHost extends DomQueryHost, DomEventHost, DomMutationHost, ExecutionHost, NotificationHost {
    withButtonDisabled: <T>(button: Element, functionValue: () => Promise<T>, options?: { keepDisabled?: boolean }) => Promise<T>;
    confirmAndExecute: NonNullable<ExecutionHost['confirmAndExecute']>;
    filterSettings: () => void;
}

interface SettingsProductTaskApi {
    get: (taskId: string, options?: { signal?: AbortSignal }) => Promise<TaskResponse>;
    listActive: (options?: { taskType?: string; limit?: number; signal?: AbortSignal }) => Promise<TaskListResponse>;
}

interface SettingsUsersRenderContext {
    users: readonly WebuiUser[];
    availability: SettingsCapabilityAvailability;
    sanitizeHtml: (value: string) => string;
}

interface SettingsUsersController {
    destroy(): void;
    refresh(): Promise<boolean>;
    execute(action: string): Promise<void>;
}

interface SettingsUsersControllerHost {
    view: {
        pageDom: DomQueryHost['pageDom'];
    };
    execution: {
        confirmAndExecute: NonNullable<ExecutionHost['confirmAndExecute']>;
    };
    notifications: NotificationHost;
    state: {
        getUsers: () => WebuiUser[];
    };
}

interface SettingsUsersContribution {
    render(context: SettingsUsersRenderContext): string;
    isAction(value: string | undefined): value is string;
    createController(host: SettingsUsersControllerHost, container: HTMLElement): SettingsUsersController;
}

interface SettingsEditionContribution {
    readonly tabs: readonly NormalTabDefinition[];
    createManagers(host: SettingsProductManagerHost, api: OsEndpoints, tasks: SettingsProductTaskApi): ReadonlyMap<string, SettingsProductManager>;
    createUsers(api: OsEndpoints['users']): SettingsUsersContribution;
}

export type { SettingsEditionContribution, SettingsProductManager, SettingsProductManagerHost, SettingsProductTaskApi, SettingsUsersContribution, SettingsUsersController, SettingsUsersControllerHost, SettingsUsersRenderContext };
