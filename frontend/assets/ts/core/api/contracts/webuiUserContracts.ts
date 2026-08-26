/* SoAI - Frontend WebUI user endpoint contracts [frontend/assets/ts/core/api/contracts/webuiUserContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { readRequiredNonNegativeIntegerValue, readRequiredPositiveSafeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { assertExactRecordKeys, requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredBooleanValue, readRequiredStringValue } from '@core/types/payloadValueReaders.ts';
import type { OpaqueJsonObject } from '@core/api/contracts/opaquePayload.ts';
import { requireCanonicalUsername } from '@core/users/username.ts';
import { decodeWizardCompletedSummary, decodeWizardStatusLookupResponse, decodeWizardStatusResponse, type WizardCompletedSummary, type WizardStatusLookupResponse, type WizardStatusResponse } from '@core/api/contracts/wizardLicensingContracts.ts';

interface MessageResponse {
    message: string;
}

interface WebuiUser {
    id: number;
    username: string;
    isAdmin: boolean;
    workspacePath: string;
    workspacePathResolved: string;
    defaultWorkspacePath: string;
    identityRevision: number;
}

interface WizardCompleteResponse extends MessageResponse {
    user: WebuiUser;
    completion: WizardCompletedSummary;
}

interface PasswordVaultResetResponse extends MessageResponse {
    deletedCredentials: number;
    clearedSecretHandles: number;
}

const decodeMessageResponse = (value: ApiResponsePayload, label: string): MessageResponse => {
    const record = requireRecord(value, label);
    return { message: readRequiredStringValue(record['message'], `${label}.message`) };
};

const decodeWebuiUser = (value: ApiResponsePayload, label: string): WebuiUser => {
    const record = requireRecord(value, label);
    const username = readRequiredStringValue(record['username'], `${label}.username`);
    const workspacePath = readRequiredStringValue(record['workspace_path'], `${label}.workspace_path`);
    const workspacePathResolved = readRequiredStringValue(record['workspace_path_resolved'], `${label}.workspace_path_resolved`);
    const defaultWorkspacePath = readRequiredStringValue(record['default_workspace_path'], `${label}.default_workspace_path`);
    if (!username || requireCanonicalUsername(username) !== username || !workspacePath || !workspacePathResolved || !defaultWorkspacePath) {
        throw new TypeError(`${label} contains an empty required string`);
    }
    return {
        id: readRequiredPositiveSafeIntegerValue(record['id'], `${label}.id`),
        username,
        isAdmin: readRequiredBooleanValue(record['is_admin'], `${label}.is_admin`),
        workspacePath,
        workspacePathResolved,
        defaultWorkspacePath,
        identityRevision: readRequiredPositiveSafeIntegerValue(record['identity_revision'], `${label}.identity_revision`)
    };
};

const decodeWebuiUsers = (value: ApiResponsePayload): WebuiUser[] => {
    if (!Array.isArray(value)) {
        throw new TypeError('WebUI users list response must be an array');
    }
    return value.map((entry, index) => decodeWebuiUser(entry, `WebUI user entry at index ${index}`));
};

const decodeWizardCompleteResponse = (value: ApiResponsePayload): WizardCompleteResponse => {
    const record = requireRecord(value, 'Wizard complete response');
    assertExactRecordKeys(record, ['message', 'user', 'completion'], 'Wizard complete response');
    const completion = decodeWizardCompletedSummary(record['completion']);
    if (completion === null) throw new TypeError('Wizard complete response.completion is required.');
    return { message: readRequiredStringValue(record['message'], 'Wizard complete response.message'), user: decodeWebuiUser(record['user'], 'Wizard complete response.user'), completion };
};

const decodePasswordVaultResetResponse = (value: ApiResponsePayload): PasswordVaultResetResponse => {
    const record = requireRecord(value, 'Password vault reset response');
    return { message: readRequiredStringValue(record['message'], 'Password vault reset response.message'), deletedCredentials: readRequiredNonNegativeIntegerValue(record['deleted_credentials'], 'Password vault reset response.deleted_credentials'), clearedSecretHandles: readRequiredNonNegativeIntegerValue(record['cleared_secret_handles'], 'Password vault reset response.cleared_secret_handles') };
};

const decodeOpaquePreferencesResponse = (value: ApiResponsePayload, label: string): OpaqueJsonObject => requireRecord(value, label);

export { decodeMessageResponse, decodeOpaquePreferencesResponse, decodePasswordVaultResetResponse, decodeWebuiUser, decodeWebuiUsers, decodeWizardCompleteResponse, decodeWizardStatusLookupResponse, decodeWizardStatusResponse };
export type { MessageResponse, PasswordVaultResetResponse, WebuiUser, WizardCompleteResponse, WizardStatusLookupResponse, WizardStatusResponse };
