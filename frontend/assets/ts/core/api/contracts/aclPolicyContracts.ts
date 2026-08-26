/* SoAI - Frontend ACL policy API contracts [frontend/assets/ts/core/api/contracts/aclPolicyContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireJsonResponsePayload } from '@core/api/jsonResponsePayload.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { readRequiredTrimmedStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import { readRequiredFiniteNumberValue } from '@core/types/payloadNumberReaders.ts';
import { readRequiredJsonObjectArrayValue, requireRecord } from '@core/types/payloadRecordReaders.ts';
import { isAllowedStringValue, readRequiredBooleanValue, readRequiredNonEmptyStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

type AclRoleId = 'ADMIN' | 'STANDARD' | 'UNINITIALIZED' | 'ANONYMOUS';

interface AclCatalogRole {
    id: AclRoleId;
    mutable: boolean;
    order: number;
}

interface AclCatalogAction {
    id: string;
    roles: AclRoleId[];
    lockedRoles: AclRoleId[];
    order: number;
}

interface AclPolicyCatalog {
    roles: AclCatalogRole[];
    actions: AclCatalogAction[];
}

interface AclPolicyResponse {
    effective: Record<string, string[]>;
    defaults: Record<string, string[]>;
    overrides: Record<string, string[]>;
    catalog: AclPolicyCatalog;
}

type AclPolicyOverrides = Partial<Record<AclRoleId, string[]>>;

const ACL_ROLE_IDS: readonly AclRoleId[] = ['ADMIN', 'STANDARD', 'UNINITIALIZED', 'ANONYMOUS'];

const isAclRoleId = (value: JsonValue | null | undefined): value is AclRoleId => isAllowedStringValue(value, ACL_ROLE_IDS);

const decodeAclRole = (value: JsonValue, index: number): AclCatalogRole => {
    const record = requireRecord(value, `ACL policy catalog.roles[${String(index)}]`);
    const id = record['id'];
    if (!isAclRoleId(id)) throw new TypeError(`ACL policy catalog.roles[${String(index)}].id is invalid`);
    return {
        id,
        mutable: readRequiredBooleanValue(record['mutable'], `ACL policy catalog.roles[${String(index)}].mutable`),
        order: readRequiredFiniteNumberValue(record['order'], `ACL policy catalog.roles[${String(index)}].order`)
    };
};

const decodeAclRoleList = (value: JsonValue | undefined, label: string): AclRoleId[] =>
    readRequiredTrimmedStringArrayValue(value, label).map((entry, index) => {
        if (!isAclRoleId(entry)) throw new TypeError(`${label}[${String(index)}] is invalid`);
        return entry;
    });

const decodeAclAction = (value: JsonValue, index: number): AclCatalogAction => {
    const record = requireRecord(value, `ACL policy catalog.actions[${String(index)}]`);
    return {
        id: readRequiredNonEmptyStringValue(record['id'], `ACL policy catalog.actions[${String(index)}].id`),
        roles: decodeAclRoleList(record['roles'], `ACL policy catalog.actions[${String(index)}].roles`),
        lockedRoles: decodeAclRoleList(record['locked_roles'], `ACL policy catalog.actions[${String(index)}].locked_roles`),
        order: readRequiredFiniteNumberValue(record['order'], `ACL policy catalog.actions[${String(index)}].order`)
    };
};

const decodeAclRoleActionMap = (value: JsonValue | undefined, label: string, actionIds: ReadonlySet<string>): Record<string, string[]> => {
    const record = requireRecord(value, label);
    const result: Record<string, string[]> = {};
    for (const key of Object.keys(record)) {
        if (!isAclRoleId(key)) throw new TypeError(`${label}.${key} role is invalid`);
        result[key] = readRequiredTrimmedStringArrayValue(record[key], `${label}.${key}`).map((actionId, index) => {
            if (!actionIds.has(actionId)) throw new TypeError(`${label}.${key}[${String(index)}] action is invalid`);
            return actionId;
        });
    }
    return result;
};

const decodeAclPolicyResponse = (value: ApiResponsePayload): AclPolicyResponse => {
    const policy = requireRecord(requireJsonResponsePayload(value, 'ACL policy response'), 'ACL policy response');
    const catalogRecord = requireRecord(policy['catalog'], 'ACL policy catalog');
    const catalog: AclPolicyCatalog = {
        roles: readRequiredJsonObjectArrayValue(catalogRecord['roles'], 'ACL policy catalog.roles').map(decodeAclRole),
        actions: readRequiredJsonObjectArrayValue(catalogRecord['actions'], 'ACL policy catalog.actions').map(decodeAclAction)
    };
    const actionIds = new Set(catalog.actions.map((action) => action.id));
    return {
        effective: decodeAclRoleActionMap(policy['effective'], 'ACL policy effective', actionIds),
        defaults: decodeAclRoleActionMap(policy['defaults'], 'ACL policy defaults', actionIds),
        overrides: decodeAclRoleActionMap(policy['overrides'], 'ACL policy overrides', actionIds),
        catalog
    };
};

const serializeAclPolicyUpdateRequest = (overrides: AclPolicyOverrides): JsonObject => {
    const serializedOverrides: JsonObject = {};
    for (const [role, actions] of Object.entries(overrides)) if (actions) serializedOverrides[role] = actions.slice();
    return { overrides: serializedOverrides };
};

export { decodeAclPolicyResponse, serializeAclPolicyUpdateRequest };
export type { AclCatalogAction, AclCatalogRole, AclPolicyCatalog, AclPolicyOverrides, AclPolicyResponse, AclRoleId };
