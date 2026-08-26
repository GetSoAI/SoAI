/* SoAI - Settings page acl manager markup [frontend/assets/ts/pages/settings/controllers/aclManagerMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderAdminOnlyNotice } from '@core/settings/adminOnlyNotice.ts';
import { createSettingsManualFieldKey } from '@core/settings/settingsFieldKeys.ts';
import { renderSection, renderSettingItem, renderSettingsGroup, renderSettingsSubgroup, renderToggleControl } from '@core/settings/settingsMarkup.ts';
import { getPreferenceStateLabels, renderSettingsCapabilityNotice, type SettingsCapabilityAvailability } from '@features/settings/public.ts';
import type { AclCatalogAction, AclCatalogRole, AclPolicyResponse } from '@core/api/contracts/aclPolicyContracts.ts';
import { resolveAclActionDescription, resolveAclActionLabel } from '@pages/settings/controllers/aclActionText.ts';
import type { AclManagerHost } from '@pages/settings/controllers/AclManagerSupport.ts';
import { resolveAclActionsForRole, resolveAclActiveActions, resolveAclRoles } from '@pages/settings/controllers/aclPolicyState.ts';

const resolveRoleLabel = (role: AclCatalogRole['id']): string => {
    switch (role) {
        case 'UNINITIALIZED':
            return i18n.t('settings.acl.bootstrapRole');
        case 'ANONYMOUS':
            return i18n.t('settings.acl.anonymousRole');
        case 'ADMIN':
            return i18n.t('settings.acl.adminRole');
        case 'STANDARD':
            return i18n.t('settings.acl.standardRole');
    }
};

const resolveRoleDescription = (role: AclCatalogRole['id']): string => {
    switch (role) {
        case 'UNINITIALIZED':
            return i18n.t('settings.acl.bootstrapRoleDescription');
        case 'ANONYMOUS':
            return i18n.t('settings.acl.anonymousRoleDescription');
        case 'ADMIN':
            return i18n.t('settings.acl.adminRoleDescription');
        case 'STANDARD':
            return i18n.t('settings.acl.standardRoleDescription');
    }
};

const renderActionItem = (action: AclCatalogAction, role: AclCatalogRole, activeActions: ReadonlySet<string>, trueLabel: string, falseLabel: string): string => {
    const isLocked = !role.mutable || action.lockedRoles.includes(role.id);
    const isChecked = activeActions.has(action.id);
    const wrapperDataset = isLocked ? { tooltip: i18n.t('settings.acl.lockedAction') } : undefined;
    return renderSettingItem({
        label: resolveAclActionLabel(action.id),
        help: resolveAclActionDescription(action.id),
        className: isLocked ? 'acl-item-locked' : '',
        fieldKey: createSettingsManualFieldKey(createAclActionFieldKey(role.id, action.id)),
        control: renderToggleControl({
            id: createAclActionFieldKey(role.id, action.id),
            checked: isChecked,
            disabled: isLocked,
            labels: { trueLabel, falseLabel },
            inputDataset: {
                aclAction: action.id,
                aclRole: role.id
            },
            ...(wrapperDataset ? { wrapperDataset } : {})
        })
    });
};

const createAclActionFieldKey = (roleId: string, actionId: string): string => `acl:${roleId}:${actionId}`;

const renderRoleSection = (role: AclCatalogRole, aclPolicy: AclPolicyResponse | null, trueLabel: string, falseLabel: string): string | null => {
    const actions = resolveAclActionsForRole(aclPolicy, role.id);
    if (actions.length === 0) {
        return null;
    }
    const activeActions = new Set(resolveAclActiveActions(aclPolicy, role.id));
    const items = actions.map((action) => renderActionItem(action, role, activeActions, trueLabel, falseLabel));
    return renderSettingsSubgroup({
        title: resolveRoleLabel(role.id),
        description: resolveRoleDescription(role.id),
        content: renderSettingsGroup(items)
    });
};

const renderAclManagerMarkup = (host: AclManagerHost, availability: SettingsCapabilityAvailability): TrustedHtml => {
    if (!host.isAdmin()) {
        return toTrustedUiHtml(
            renderSection({
                title: i18n.t('settings.acl.sectionTitle'),
                description: i18n.t('settings.acl.sectionDescription'),
                className: 'settings-section--acl',
                content: renderAdminOnlyNotice(i18n.t('settings.adminOnlyRequired')).html
            })
        );
    }

    const aclPolicy = host.getAclPolicy();
    const toggleLabels = getPreferenceStateLabels();
    const trueLabel = host.sanitizeAttribute(toggleLabels.trueLabel);
    const falseLabel = host.sanitizeAttribute(toggleLabels.falseLabel);
    const roleSections = resolveAclRoles(aclPolicy)
        .map((role) => renderRoleSection(role, aclPolicy, trueLabel, falseLabel))
        .filter((section): section is string => section !== null)
        .join('');

    return toTrustedUiHtml(
        renderSection({
            title: i18n.t('settings.acl.sectionTitle'),
            description: i18n.t('settings.acl.sectionDescription'),
            className: 'settings-section--acl',
            content: `${renderSettingsCapabilityNotice(availability)}${roleSections}`
        })
    );
};

export { createAclActionFieldKey, renderAclManagerMarkup };
