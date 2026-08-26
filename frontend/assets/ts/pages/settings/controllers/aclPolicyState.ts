/* SoAI - Settings page acl policy state [frontend/assets/ts/pages/settings/controllers/aclPolicyState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { filterStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import type { AclCatalogAction, AclCatalogRole, AclPolicyResponse } from '@core/api/contracts/aclPolicyContracts.ts';

type AclRole = 'ADMIN' | 'STANDARD' | 'UNINITIALIZED' | 'ANONYMOUS';

const sortByOrder = <T extends { order: number }>(items: ReadonlyArray<T>): T[] => [...items].sort((left, right) => left.order - right.order);

const resolveAclRoles = (policy: AclPolicyResponse | null): AclCatalogRole[] => {
    return policy ? sortByOrder(policy.catalog.roles) : [];
};

const resolveAclActionsForRole = (policy: AclPolicyResponse | null, role: AclRole): AclCatalogAction[] => {
    if (!policy) {
        return [];
    }
    return sortByOrder(policy.catalog.actions.filter((action) => action.roles.includes(role)));
};

const resolveAclActiveActions = (policy: AclPolicyResponse | null, role: AclRole): string[] => {
    const roleActions = policy?.effective[role];
    const normalizedRoleActions = filterStringArrayValue(roleActions);
    if (!normalizedRoleActions.length && !Array.isArray(roleActions)) {
        return resolveAclActionsForRole(policy, role).map((action) => action.id);
    }
    return normalizedRoleActions;
};

export { resolveAclActionsForRole, resolveAclActiveActions, resolveAclRoles };
export type { AclRole };
