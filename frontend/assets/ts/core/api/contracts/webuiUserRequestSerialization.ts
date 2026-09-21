/* SoAI - Frontend WebUI user request serialization [frontend/assets/ts/core/api/contracts/webuiUserRequestSerialization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OpaqueJsonObject } from '@core/api/contracts/opaquePayload.ts';
import type { IdentityMutationType } from '@core/users/identityMutationContract.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

interface IdentityMutationFinalization {
    operationType: IdentityMutationType;
    targetUserId: number;
    requestedUsername?: string;
}

const serializeLoginRequest = (username: string, password: string): JsonObject => ({ username, password });
const serializePasswordChangeRequest = (operationId: string, currentPassword: string, newPassword: string): JsonObject => ({ 'operation_id': operationId, 'current_password': currentPassword, 'new_password': newPassword });
const serializeSessionRotationRecoveryRequest = (operationId: string | null): JsonObject => (operationId === null ? {} : { 'operation_id': operationId });
const serializeUserCreateRequest = (username: string, password: string, isAdmin: boolean): JsonObject => ({ username, password, 'is_admin': isAdmin });
const serializeUserAdminUpdateRequest = (isAdmin: boolean): JsonObject => ({ 'is_admin': isAdmin });
const serializeUsernameRenameRequest = (operationId: string, newUsername: string, currentPassword: string): JsonObject => ({ 'operation_id': operationId, 'new_username': newUsername, 'current_password': currentPassword });
const serializeMutationStatusRequest = (finalization: IdentityMutationFinalization | undefined): JsonObject =>
    finalization === undefined
        ? {}
        : {
              'finalize_absence': true,
              'operation_type': finalization.operationType,
              'target_user_id': finalization.targetUserId,
              ...(finalization.requestedUsername === undefined ? {} : { 'requested_username': finalization.requestedUsername })
          };
const serializeWorkspacePathRequest = (workspacePath: string | null): JsonObject => ({ 'workspace_path': workspacePath });
const serializePreferencesUpdateRequest = (preferences: OpaqueJsonObject, intendedUserId?: number): JsonObject => ({ preferences, ...(intendedUserId === undefined ? {} : { 'intended_user_id': intendedUserId }) });
const serializeWizardCompleteRequest = (draftRevision: number, username: string, password: string, language: string): JsonObject => ({ 'schema_version': 1, 'draft_revision': draftRevision, username, password, language });

export { serializeLoginRequest, serializeMutationStatusRequest, serializePasswordChangeRequest, serializePreferencesUpdateRequest, serializeSessionRotationRecoveryRequest, serializeUserAdminUpdateRequest, serializeUserCreateRequest, serializeUsernameRenameRequest, serializeWizardCompleteRequest, serializeWorkspacePathRequest };
export type { IdentityMutationFinalization };
