/* SoAI - Settings page ACL policy overrides service [frontend/assets/ts/pages/settings/controllers/aclpolicyoverrides/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { requireTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { dom } from '@core/dom/dom.ts';
import { narrowInput } from '@core/dom/narrowElement.ts';
import { getCurrentLocale } from '@core/languageservice/service.ts';
import { uniqueSortedStrings } from '@core/normalize.ts';
import { arraysEqual } from '@core/primitives/equality.ts';
import { isPlainObject } from '@core/typeGuards.ts';
import { filterStringArrayValue, filterTrimmedStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import type { AclPolicyResponse } from '@core/api/contracts/aclPolicyContracts.ts';
import { resolveAclActionsForRole } from '@pages/settings/controllers/aclPolicyState.ts';

type AclMutableRole = 'ADMIN' | 'STANDARD';
type AclOverridePatch = Partial<Record<AclMutableRole, string[]>>;
type AclRoleActionMap = Record<AclMutableRole, string[]>;

const ACL_MUTABLE_ROLES: readonly AclMutableRole[] = ['ADMIN', 'STANDARD'];

const collectAclActionCheckboxes = (root: HTMLElement): HTMLInputElement[] => {
    const elements = dom.resolveAll('input[data-acl-action]', root);
    const checkboxes: HTMLInputElement[] = [];
    elements.forEach((element) => {
        const input = narrowInput(element, 'ACL action control');
        if (input.type !== 'checkbox') {
            throw new TypeError('ACL action control must be a checkbox input');
        }
        checkboxes.push(input);
    });
    return checkboxes;
};

const createEmptyRoleActionMap = (): AclRoleActionMap => ({ ADMIN: [], STANDARD: [] });

const normalizeAclRoleActionMap = (value: JsonValue | undefined): AclRoleActionMap => {
    const raw = isPlainObject(value) ? value : {};
    return {
        ADMIN: uniqueSortedStrings(filterTrimmedStringArrayValue(raw['ADMIN']), getCurrentLocale()),
        STANDARD: uniqueSortedStrings(filterTrimmedStringArrayValue(raw['STANDARD']), getCurrentLocale())
    };
};

const resolveBackendDefaultActions = (policy: AclPolicyResponse): AclRoleActionMap => {
    const defaults = policy.defaults;
    if (defaults) {
        return normalizeAclRoleActionMap(defaults);
    }
    return {
        ADMIN: uniqueSortedStrings(
            resolveAclActionsForRole(policy, 'ADMIN').map((action) => action.id),
            getCurrentLocale()
        ),
        STANDARD: uniqueSortedStrings(
            resolveAclActionsForRole(policy, 'STANDARD').map((action) => action.id),
            getCurrentLocale()
        )
    };
};

const computeAclSelectedActions = (root: HTMLElement): AclRoleActionMap => {
    const selectedActions = createEmptyRoleActionMap();
    const checkboxes = collectAclActionCheckboxes(root);
    checkboxes.forEach((checkbox) => {
        if (!checkbox.checked) {
            return;
        }
        const action = requireTrimmedDataAttribute(checkbox, 'aclAction', 'ACL action checkbox');
        const role = requireTrimmedDataAttribute(checkbox, 'aclRole', 'ACL action checkbox');
        if (role !== 'ADMIN' && role !== 'STANDARD') {
            return;
        }
        selectedActions[role].push(action);
    });
    return {
        ADMIN: uniqueSortedStrings(selectedActions.ADMIN, getCurrentLocale()),
        STANDARD: uniqueSortedStrings(selectedActions.STANDARD, getCurrentLocale())
    };
};

const resolveRenderedActionSet = (policy: AclPolicyResponse, role: AclMutableRole): ReadonlySet<string> => {
    return new Set(resolveAclActionsForRole(policy, role).map((action) => action.id));
};

const resolvePreservedNonRenderedActions = (policy: AclPolicyResponse, role: AclMutableRole, renderedActions: ReadonlySet<string>): string[] => {
    return normalizeAclEffectiveActions(policy, role).filter((actionId) => !renderedActions.has(actionId));
};

const mergeVisibleAndPreservedActions = (visibleActions: readonly string[], preservedActions: readonly string[]): string[] => {
    return uniqueSortedStrings([...visibleActions, ...preservedActions], getCurrentLocale());
};

const computeAclOverrides = (root: HTMLElement, policy: AclPolicyResponse): AclOverridePatch => {
    const selectedActions = computeAclSelectedActions(root);
    const defaultActions = resolveBackendDefaultActions(policy);
    const overrides: AclOverridePatch = {};
    for (const role of ACL_MUTABLE_ROLES) {
        const renderedActions = resolveRenderedActionSet(policy, role);
        const preservedActions = resolvePreservedNonRenderedActions(policy, role, renderedActions);
        const nextActions = mergeVisibleAndPreservedActions(selectedActions[role], preservedActions);
        if (!arraysEqual(nextActions, defaultActions[role])) {
            overrides[role] = nextActions;
        }
    }
    return overrides;
};

const normalizeAclOverrides = (value: JsonValue | undefined): AclOverridePatch => {
    const raw = isPlainObject(value) ? value : {};
    const normalizeList = (list: JsonValue | undefined): string[] => uniqueSortedStrings(filterTrimmedStringArrayValue(list), getCurrentLocale());
    const overrides: AclOverridePatch = {};
    for (const role of ACL_MUTABLE_ROLES) {
        if (Array.isArray(raw[role])) {
            overrides[role] = normalizeList(raw[role]);
        }
    }
    return overrides;
};

const normalizeAclEffectiveActions = (policy: AclPolicyResponse, role: AclMutableRole): string[] => uniqueSortedStrings(filterStringArrayValue(policy.effective[role]), getCurrentLocale());

const areAclOverridesEqual = (left: AclOverridePatch, right: AclOverridePatch): boolean => {
    for (const role of ACL_MUTABLE_ROLES) {
        const leftHasRole = Array.isArray(left[role]);
        const rightHasRole = Array.isArray(right[role]);
        if (leftHasRole !== rightHasRole) {
            return false;
        }
        const leftValues = left[role];
        const rightValues = right[role];
        if (Array.isArray(leftValues) && Array.isArray(rightValues) && !arraysEqual(leftValues, rightValues)) {
            return false;
        }
    }
    return true;
};

export { areAclOverridesEqual, collectAclActionCheckboxes, computeAclOverrides, normalizeAclEffectiveActions, normalizeAclOverrides };
export type { AclMutableRole, AclOverridePatch };
