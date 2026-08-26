/* SoAI - Settings page users manager contracts [frontend/assets/ts/pages/settings/controllers/usersmanager/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DomEventHost, DomMutationHost, DomQueryHost, ExecutionHost, NotificationHost } from '@core/ui/controllerHosts.ts';
import type { OsOperationResponse } from '@core/api/contracts/osOperationContracts.ts';
import type { OsSystemUserInfo, OsUserMappingResponse, OsUserSyncStatus } from '@core/api/contracts/osSystemContracts.ts';
import type { FileExplorerListResponse, FileExplorerSearchResponse } from '@core/api/contracts/fileExplorerContractTypes.ts';
import type { FileBrowserListOptions, FileBrowserSearchOptions } from '@core/fileexplorerbrowser/types.ts';
import type { SignalOptions } from '@core/api/requestOptions.ts';
import type { WebuiSession } from '@core/api/contracts/webuiSessionContracts.ts';
import type { MessageResponse, WebuiUser } from '@core/api/contracts/webuiUserContracts.ts';
import type { IdentityMutationSuccess } from '@core/api/contracts/webuiIdentityMutationContracts.ts';
import type { SettingsCapabilityAvailability } from '@features/settings/public.ts';
import type { SettingsUsersContribution, SettingsUsersControllerHost } from '@core/edition/settingsContribution.ts';

interface UsersManagerDependencies {
    host: UsersManagerHost;
    productContribution: SettingsUsersContribution | null;
}

interface UsersManagerApiHost {
    listUsers: () => Promise<WebuiUser[]>;
    createUser: (username: string, password: string, isAdmin: boolean) => Promise<WebuiUser>;
    updateUser: (userId: number, isAdmin: boolean) => Promise<WebuiUser>;
    changeOwnPassword: (operationId: string, current: string, newPassword: string) => Promise<IdentityMutationSuccess>;
    changeUserPassword: (userId: number, operationId: string, current: string, newPassword: string, signal: AbortSignal) => Promise<IdentityMutationSuccess>;
    renameOwnUsername: (operationId: string, newUsername: string, currentPassword: string) => Promise<IdentityMutationSuccess>;
    renameUser: (userId: number, operationId: string, newUsername: string, currentPassword: string, signal: AbortSignal) => Promise<IdentityMutationSuccess>;
    listWorkspaceBrowser: (options?: FileBrowserListOptions) => Promise<FileExplorerListResponse>;
    searchWorkspaceBrowser: (options: FileBrowserSearchOptions) => Promise<FileExplorerSearchResponse>;
    updateUserWorkspacePath: (userId: number, workspacePath: string | null) => Promise<WebuiUser>;
    deleteUser: (userId: number) => Promise<void>;
    logout: () => Promise<void>;
    invalidateSession: () => Promise<void>;
    listSessions: (options?: SignalOptions) => Promise<WebuiSession[]>;
    revokeSession: (jti: string) => Promise<MessageResponse>;
    revokeAllSessions: () => Promise<MessageResponse>;
}

interface UsersManagerOsUsersApiHost {
    status: (options?: { signal?: AbortSignal }) => Promise<OsUserSyncStatus>;
    mapping: (options?: { signal?: AbortSignal }) => Promise<OsUserMappingResponse>;
    sync: (payload: { webuiUserId: number }, options?: { signal?: AbortSignal }) => Promise<OsSystemUserInfo | OsOperationResponse>;
    lock: (payload: { webuiUserId: number }, options?: { signal?: AbortSignal }) => Promise<OsOperationResponse>;
    sshKeys: (payload: { webuiUserId: number; publicKeys?: readonly string[] }, options?: { signal?: AbortSignal }) => Promise<OsOperationResponse>;
}

interface UsersManagerDomHost extends DomQueryHost, DomEventHost, DomMutationHost {}

interface UsersManagerExecutionHost extends ExecutionHost {
    runPageTask: <T>(name: string, functionValue: () => Promise<T>, options?: { displayName?: string }) => Promise<T | null>;
    withButtonDisabled: <T>(btn: Element, functionValue: () => Promise<T>, options?: { keepDisabled?: boolean }) => Promise<T>;
    confirmAndExecute: NonNullable<ExecutionHost['confirmAndExecute']>;
}

interface UsersManagerStateHost {
    getUsers: () => WebuiUser[];
    setUsers: (users: WebuiUser[]) => void;
    getUsersAvailability: () => SettingsCapabilityAvailability;
    setUsersAvailability: (availability: SettingsCapabilityAvailability) => void;
    getCurrentUserId: () => string | null;
    canAdministerUsers: () => boolean;
}

interface UsersManagerViewHost extends UsersManagerDomHost {
    sanitizeHtml: (value: string) => string;
}

interface UsersManagerHost extends SettingsUsersControllerHost {
    api: UsersManagerApiHost;
    view: UsersManagerViewHost;
    execution: UsersManagerExecutionHost;
    notifications: NotificationHost;
    state: UsersManagerStateHost;
    filterSettings: () => void;
}

interface UsersManagerActionContext {
    host: UsersManagerHost;
    reloadUsers: () => Promise<void>;
}

interface UsersManagerInteractionContext extends UsersManagerActionContext {
    signal: AbortSignal;
    getUserById: (userId: string) => WebuiUser | null;
    shouldPreventAdminDemotion: (userId: string) => boolean;
    shouldPreventUserDeletion: (userId: string) => boolean;
    isCurrentUser: (user: WebuiUser) => boolean;
    applyUserResult: (user: WebuiUser) => void;
}

interface UserStats {
    totalUsers: number;
    adminCount: number;
}

type UserRole = 'admin' | 'user';

export { type UsersManagerActionContext, type UsersManagerDependencies, type UsersManagerDomHost, type UsersManagerExecutionHost, type UsersManagerHost, type UsersManagerInteractionContext, type UserRole, type UserStats, type UsersManagerApiHost, type UsersManagerStateHost, type UsersManagerOsUsersApiHost };
