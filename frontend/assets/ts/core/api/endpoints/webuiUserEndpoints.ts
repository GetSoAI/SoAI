/* SoAI - WebUI user API endpoints [frontend/assets/ts/core/api/endpoints/webuiUserEndpoints.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import { decodeNoContentResponse } from '@core/api/contracts/noContentContract.ts';
import type { OpaqueJsonObject } from '@core/api/contracts/opaquePayload.ts';
import { decodeTerminalAccessPolicy, type TerminalAccessPolicyResponse } from '@core/api/contracts/terminalAccessContracts.ts';
import { decodeWebuiSessions, type WebuiSession } from '@core/api/contracts/webuiSessionContracts.ts';
import { serializeLoginRequest, serializeMutationStatusRequest, serializePasswordChangeRequest, serializePreferencesUpdateRequest, serializeSessionRotationRecoveryRequest, serializeUserAdminUpdateRequest, serializeUserCreateRequest, serializeUsernameRenameRequest, serializeWizardCompleteRequest, serializeWorkspacePathRequest, type IdentityMutationFinalization } from '@core/api/contracts/webuiUserRequestSerialization.ts';
import { buildQueryRequestOptions, buildSignalRequestOptions, type AuthTransitionSignalOptions, type SignalOptions } from '@core/api/requestOptions.ts';
import { decodeMessageResponse, decodeOpaquePreferencesResponse, decodePasswordVaultResetResponse, decodeWebuiUser, decodeWebuiUsers, decodeWizardCompleteResponse, decodeWizardStatusLookupResponse, type MessageResponse, type PasswordVaultResetResponse, type WebuiUser, type WizardCompleteResponse, type WizardStatusLookupResponse } from '@core/api/contracts/webuiUserContracts.ts';
import type { ApiQueryParameters } from '@core/api/types/request.ts';
import type { FileBrowserListOptions, FileBrowserSearchOptions } from '@core/fileexplorerbrowser/types.ts';
import { decodeFileExplorerListResponse, decodeFileExplorerSearchResponse } from '@core/api/contracts/fileExplorerContracts.ts';
import type { FileExplorerListResponse, FileExplorerSearchResponse } from '@core/api/contracts/fileExplorerContractTypes.ts';
import { decodeChatMemorySnapshot, serializeChatMemoryProfileUpdate, type ChatMemoryProfileUpdateRequest, type ChatMemorySnapshot } from '@core/api/contracts/webuiMemoryContracts.ts';
import { decodeIdentityMutationStatus, decodeIdentityMutationSuccess, decodeSessionRotationRecovery, type IdentityMutationStatus, type IdentityMutationSuccess, type SessionRotationRecovery } from '@core/api/contracts/webuiIdentityMutationContracts.ts';
import { createWizardLicensingEndpoints, type WizardLicensingEndpoints } from '@core/api/endpoints/wizardLicensingEndpoints.ts';

interface WebuiUserEndpoints {
    auth: {
        login(username: string, password: string): Promise<MessageResponse>;
        logout(): Promise<MessageResponse>;
        getMe(options?: AuthTransitionSignalOptions): Promise<WebuiUser>;
        changePassword(operationId: string, current: string, newPassword: string, options?: AuthTransitionSignalOptions): Promise<IdentityMutationSuccess>;
        recoverSessionRotation(operationId: string | null, options?: AuthTransitionSignalOptions): Promise<SessionRotationRecovery>;
    };
    users: {
        list(options?: SignalOptions): Promise<WebuiUser[]>;
        current(options?: AuthTransitionSignalOptions): Promise<WebuiUser>;
        create(username: string, password: string, isAdmin: boolean): Promise<WebuiUser>;
        update(id: number, isAdmin: boolean): Promise<WebuiUser>;
        changePassword(id: number, operationId: string, current: string, newPassword: string, options?: AuthTransitionSignalOptions): Promise<IdentityMutationSuccess>;
        renameCurrent(operationId: string, newUsername: string, currentPassword: string, options?: AuthTransitionSignalOptions): Promise<IdentityMutationSuccess>;
        rename(id: number, operationId: string, newUsername: string, currentPassword: string, options?: AuthTransitionSignalOptions): Promise<IdentityMutationSuccess>;
        mutationStatus(operationId: string, finalization?: IdentityMutationFinalization, options?: AuthTransitionSignalOptions): Promise<IdentityMutationStatus>;
        updateWorkspacePath(id: number, workspacePath: string | null): Promise<WebuiUser>;
        workspaceBrowser: {
            list(options?: FileBrowserListOptions): Promise<FileExplorerListResponse>;
            search(options: FileBrowserSearchOptions): Promise<FileExplorerSearchResponse>;
        };
        delete(id: number): Promise<void>;
    };
    sessions: {
        list(options?: SignalOptions): Promise<WebuiSession[]>;
        revoke(jti: string): Promise<MessageResponse>;
        revokeAll(): Promise<MessageResponse>;
    };
    terminal: {
        policy(): Promise<TerminalAccessPolicyResponse>;
    };
    preferences: {
        get(options?: AuthTransitionSignalOptions): Promise<OpaqueJsonObject>;
        update(preferences: OpaqueJsonObject): Promise<OpaqueJsonObject>;
        resetUiPreferences(): Promise<MessageResponse>;
        resetToolApprovalPermissions(): Promise<MessageResponse>;
    };
    memory: {
        get(): Promise<ChatMemorySnapshot>;
        saveChatProfile(request: ChatMemoryProfileUpdateRequest): Promise<ChatMemorySnapshot>;
    };
    passwordVault: {
        reset(): Promise<PasswordVaultResetResponse>;
    };
    wizard: WizardLicensingEndpoints & {
        status(options?: AuthTransitionSignalOptions): Promise<WizardStatusLookupResponse>;
        complete(draftRevision: number, username: string, password: string, language: string, options?: AuthTransitionSignalOptions): Promise<WizardCompleteResponse>;
    };
}

const buildWorkspaceBrowserListRequestOptions = (options: FileBrowserListOptions | undefined): { query: ApiQueryParameters | null; signal?: AbortSignal } => {
    if (!options) {
        return buildQueryRequestOptions(null);
    }
    const query: ApiQueryParameters = {};
    if (options.path !== undefined) {
        query['path'] = options.path;
    }
    if (options.offset !== undefined) {
        query['offset'] = options.offset;
    }
    if (options.limit !== undefined) {
        query['limit'] = options.limit;
    }
    return buildQueryRequestOptions(query, options.signal);
};

const buildWorkspaceBrowserSearchRequestOptions = (options: FileBrowserSearchOptions): { query: ApiQueryParameters | null; signal?: AbortSignal } => {
    const query: ApiQueryParameters = {
        query: options.query
    };
    if (options.path !== undefined) {
        query['path'] = options.path;
    }
    if (options.offset !== undefined) {
        query['offset'] = options.offset;
    }
    if (options.limit !== undefined) {
        query['limit'] = options.limit;
    }
    if (options.caseSensitive !== undefined) {
        query['case_sensitive'] = options.caseSensitive;
    }
    if (options.includeTotal !== undefined) {
        query['include_total'] = options.includeTotal;
    }
    return buildQueryRequestOptions(query, options.signal);
};

const createWebuiUserEndpoints = (api: ApiClientContext): WebuiUserEndpoints => ({
    auth: {
        login: async (username, password): Promise<MessageResponse> => decodeMessageResponse(await api.post('/api/v1/webui/auth/login', serializeLoginRequest(username, password)), 'Login response'),
        logout: async (): Promise<MessageResponse> => decodeMessageResponse(await api.post('/api/v1/webui/auth/logout'), 'Logout response'),
        getMe: async (options: AuthTransitionSignalOptions = {}): Promise<WebuiUser> => decodeWebuiUser(await api.get('/api/v1/webui/users/me', buildSignalRequestOptions(options)), 'Current WebUI user'),
        changePassword: async (operationId, current, newPassword, options = {}): Promise<IdentityMutationSuccess> => decodeIdentityMutationSuccess(await api.patch('/api/v1/webui/users/me/password', serializePasswordChangeRequest(operationId, current, newPassword), buildSignalRequestOptions(options)), 'Password change response'),
        recoverSessionRotation: async (operationId, options = {}): Promise<SessionRotationRecovery> => decodeSessionRotationRecovery(await api.post('/api/v1/webui/auth/session-rotation/recover', serializeSessionRotationRecoveryRequest(operationId), buildSignalRequestOptions(options)))
    },
    users: {
        list: async (options: SignalOptions = {}): Promise<WebuiUser[]> => decodeWebuiUsers(await api.get('/api/v1/webui/users', buildSignalRequestOptions(options))),
        current: async (options: AuthTransitionSignalOptions = {}): Promise<WebuiUser> => decodeWebuiUser(await api.get('/api/v1/webui/users/me', buildSignalRequestOptions(options)), 'Current WebUI user'),
        create: async (username, password, isAdmin): Promise<WebuiUser> => decodeWebuiUser(await api.post('/api/v1/webui/users', serializeUserCreateRequest(username, password, isAdmin)), 'Created WebUI user'),
        update: async (id, isAdmin): Promise<WebuiUser> => decodeWebuiUser(await api.patch(`/api/v1/webui/users/${api.encodePathSegment(id)}`, serializeUserAdminUpdateRequest(isAdmin)), 'Updated WebUI user'),
        changePassword: async (id, operationId, current, newPassword, options = {}): Promise<IdentityMutationSuccess> => decodeIdentityMutationSuccess(await api.patch(`/api/v1/webui/users/${api.encodePathSegment(id)}/password`, serializePasswordChangeRequest(operationId, current, newPassword), buildSignalRequestOptions(options)), 'Admin password change response'),
        renameCurrent: async (operationId, newUsername, currentPassword, options = {}): Promise<IdentityMutationSuccess> => decodeIdentityMutationSuccess(await api.patch('/api/v1/webui/users/me/username', serializeUsernameRenameRequest(operationId, newUsername, currentPassword), buildSignalRequestOptions(options)), 'Current username rename response'),
        rename: async (id, operationId, newUsername, currentPassword, options = {}): Promise<IdentityMutationSuccess> => decodeIdentityMutationSuccess(await api.patch(`/api/v1/webui/users/${api.encodePathSegment(id)}/username`, serializeUsernameRenameRequest(operationId, newUsername, currentPassword), buildSignalRequestOptions(options)), 'Username rename response'),
        mutationStatus: async (operationId, finalization, options = {}): Promise<IdentityMutationStatus> => {
            return decodeIdentityMutationStatus(await api.post(`/api/v1/webui/users/mutations/${api.encodePathSegment(operationId)}/status`, serializeMutationStatusRequest(finalization), buildSignalRequestOptions(options)));
        },
        updateWorkspacePath: async (id, workspacePath): Promise<WebuiUser> => decodeWebuiUser(await api.patch(`/api/v1/webui/users/${api.encodePathSegment(id)}/workspace-path`, serializeWorkspacePathRequest(workspacePath)), 'Updated WebUI user workspace'),
        workspaceBrowser: {
            list: async (options): Promise<FileExplorerListResponse> => decodeFileExplorerListResponse(await api.get('/api/v1/webui/users/workspace-browser/list', buildWorkspaceBrowserListRequestOptions(options))),
            search: async (options): Promise<FileExplorerSearchResponse> => decodeFileExplorerSearchResponse(await api.get('/api/v1/webui/users/workspace-browser/search', buildWorkspaceBrowserSearchRequestOptions(options)))
        },
        delete: async (id): Promise<void> => decodeNoContentResponse(await api.delete(`/api/v1/webui/users/${api.encodePathSegment(id)}`), 'WebUI user delete response')
    },
    sessions: {
        list: async (options: SignalOptions = {}): Promise<WebuiSession[]> => decodeWebuiSessions(await api.get('/api/v1/webui/sessions', buildSignalRequestOptions(options))),
        revoke: async (jti): Promise<MessageResponse> => decodeMessageResponse(await api.delete(`/api/v1/webui/sessions/${api.encodePathSegment(jti)}`), 'Session revoke response'),
        revokeAll: async (): Promise<MessageResponse> => decodeMessageResponse(await api.delete('/api/v1/webui/sessions', buildSignalRequestOptions({ authTransitionOwned: true })), 'All sessions revoke response')
    },
    terminal: {
        policy: async (): Promise<TerminalAccessPolicyResponse> => decodeTerminalAccessPolicy(await api.get('/api/v1/webui/terminal/policy'))
    },
    preferences: {
        get: async (options = {}): Promise<OpaqueJsonObject> => decodeOpaquePreferencesResponse(await api.get('/api/v1/webui/users/me/preferences', buildSignalRequestOptions(options)), 'Preferences response'),
        update: async (preferences): Promise<OpaqueJsonObject> => decodeOpaquePreferencesResponse(await api.patch('/api/v1/webui/users/me/preferences', serializePreferencesUpdateRequest(preferences)), 'Preferences update response'),
        resetUiPreferences: async (): Promise<MessageResponse> => decodeMessageResponse(await api.post('/api/v1/webui/users/me/preferences/reset'), 'Preferences reset response'),
        resetToolApprovalPermissions: async (): Promise<MessageResponse> => decodeMessageResponse(await api.post('/api/v1/webui/users/me/tool-approval-permissions/reset'), 'Tool approval reset response')
    },
    memory: {
        get: async (): Promise<ChatMemorySnapshot> => decodeChatMemorySnapshot(await api.get('/api/v1/webui/users/me/memory')),
        saveChatProfile: async (request): Promise<ChatMemorySnapshot> => decodeChatMemorySnapshot(await api.put('/api/v1/webui/users/me/memory/chat-profile', serializeChatMemoryProfileUpdate(request)))
    },
    passwordVault: {
        reset: async (): Promise<PasswordVaultResetResponse> => decodePasswordVaultResetResponse(await api.post('/api/v1/webui/users/me/password-vault/reset'))
    },
    wizard: {
        ...createWizardLicensingEndpoints(api),
        status: async (options: AuthTransitionSignalOptions = {}): Promise<WizardStatusLookupResponse> => decodeWizardStatusLookupResponse(await api.get('/api/v1/webui/wizard/status', { cache: 'no-store', ...buildSignalRequestOptions(options) })),
        complete: async (draftRevision, username, password, language, options: AuthTransitionSignalOptions = {}): Promise<WizardCompleteResponse> => decodeWizardCompleteResponse(await api.post('/api/v1/webui/wizard/complete', serializeWizardCompleteRequest(draftRevision, username, password, language), buildSignalRequestOptions(options)))
    }
});

export { createWebuiUserEndpoints };
export type { IdentityMutationFinalization, WebuiUserEndpoints };
