/* SoAI - Frontend terminal access API contracts [frontend/assets/ts/core/api/contracts/terminalAccessContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredBooleanValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';

interface TerminalAccessPolicyResponse {
    canAccessTerminal: boolean;
    adminCount: number;
    policyRevision: string;
}

const decodeTerminalAccessPolicy = (value: ApiResponsePayload): TerminalAccessPolicyResponse => {
    const record = requireRecord(value, 'Terminal access policy response');
    return {
        canAccessTerminal: readRequiredBooleanValue(record['can_access_terminal'], 'Terminal access policy response.can_access_terminal'),
        adminCount: readRequiredNonNegativeIntegerValue(record['admin_count'], 'Terminal access policy response.admin_count'),
        policyRevision: readRequiredTrimmedStringValue(record['policy_revision'], 'Terminal access policy response.policy_revision')
    };
};

export { decodeTerminalAccessPolicy };
export type { TerminalAccessPolicyResponse };
