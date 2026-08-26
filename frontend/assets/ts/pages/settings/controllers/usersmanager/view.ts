/* SoAI - Settings page users manager rendering [frontend/assets/ts/pages/settings/controllers/usersmanager/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderLabelAttributes } from '@core/security/public.ts';
import { escapeAttribute } from '@core/security/textSanitizer.ts';
import { renderSection, renderSettingsRecordList, renderSettingsSubgroup } from '@core/settings/settingsMarkup.ts';
import { renderSettingsTitlebarAddButton, renderSettingsTitlebarRefreshButton } from '@core/settings/titlebarActions.ts';
import type { WebuiUser } from '@core/api/contracts/webuiUserContracts.ts';
import { renderControlDisabledAttributes } from '@core/ui/controls/disabledState.ts';
import { renderDropdownSelectControl } from '@core/ui/dropdown/selectControl.ts';
import { renderEmptyState } from '@core/ui/emptyState.ts';
import { renderSettingsCapabilityNotice, type SettingsCapabilityAvailability } from '@features/settings/public.ts';

import { USERS_ACTION_ADD_USER, USERS_ACTION_CHANGE_PASSWORD, USERS_ACTION_CHANGE_WORKSPACE_PATH, USERS_ACTION_DELETE_USER, USERS_ACTION_LOGOUT_USER, USERS_ACTION_REFRESH, USERS_ACTION_RENAME, USERS_ACTION_SELECT_ROLE } from '@pages/settings/controllers/usersmanager/constants.ts';
import { renderSessionsContent } from '@pages/settings/controllers/usersmanager/WebuiSessions.ts';

interface UsersManagerRenderContext {
    users: readonly WebuiUser[];
    availability: SettingsCapabilityAvailability;
    sanitizeHtml: (value: string) => string;
    isCurrentUser: (userId: string) => boolean;
    canAdministerUsers: boolean;
    canChangePassword: (userId: string) => boolean;
    shouldDisableChangeRole: (userId: string) => boolean;
    shouldDisableDelete: (userId: string) => boolean;
    productSection: string;
}

const buildRoleBadgeClass = (isAdmin: boolean): string => (isAdmin ? 'settings-record-badge--warning' : 'settings-record-badge--active');

const buildUserRoleBadgeText = (isAdmin: boolean): string => {
    if (isAdmin) {
        return i18n.t('settings.users.roles.adminBadge');
    }
    return i18n.t('settings.users.roles.userBadge');
};

const buildRoleSelect = (context: { userId: string; role: 'admin' | 'user'; shouldDisableUserRole: boolean; disableRoleSelect: boolean; disabledTitle: string; sanitizeHtml: (value: string) => string }): string => {
    const { userId, role, shouldDisableUserRole, disableRoleSelect } = context;
    const userIdAttr = escapeAttribute(userId);
    const roleLabel = i18n.t('settings.users.roleButton');
    const adminLabel = i18n.t('settings.users.roleOptions.admin');
    const userLabel = i18n.t('settings.users.roleOptions.user');
    const userTitle = disableRoleSelect ? context.disabledTitle : roleLabel;
    const title = role === 'admin' ? userTitle : roleLabel;
    const disabledAttrs = renderControlDisabledAttributes(disableRoleSelect);
    return renderDropdownSelectControl({ shellClassName: 'dropdown-select--sm', selectMarkup: `<select class="user-role-select" data-action="${USERS_ACTION_SELECT_ROLE}" data-user-id="${userIdAttr}" aria-label="${escapeAttribute(roleLabel)}" data-tooltip="${escapeAttribute(title)}"${disabledAttrs}><option value="" selected disabled hidden>${context.sanitizeHtml(roleLabel)}</option><option value="admin"${role === 'admin' ? ' disabled' : ''}>${context.sanitizeHtml(adminLabel)}</option><option value="user"${role === 'user' || shouldDisableUserRole ? ' disabled' : ''}>${context.sanitizeHtml(userLabel)}</option></select>` });
};

const buildUserItem = (context: { user: WebuiUser; sanitizeHtml: (value: string) => string; isCurrentUser: (userId: string) => boolean; canChangePassword: (userId: string) => boolean; shouldDisableChangeRole: (userId: string) => boolean; shouldDisableDelete: (userId: string) => boolean; showAdminActions: boolean; showRoleSelect: boolean }): string => {
    const { user, sanitizeHtml, isCurrentUser, shouldDisableChangeRole, shouldDisableDelete } = context;
    const isAdmin = user.isAdmin;
    const role = isAdmin ? 'admin' : 'user';
    const userId = String(user.id);
    const userIdAttr = escapeAttribute(userId);
    const sanitizedUsername = sanitizeHtml(user.username);
    const usernameAttr = escapeAttribute(user.username);
    const isDefaultWorkspacePath = user.workspacePath === user.defaultWorkspacePath;
    const logoutLabel = i18n.t('header.menu.logout');
    const logoutButton = isCurrentUser(userId) ? `<button type="button" class="ui-button ui-button--sm ui-variant-neutral logout-user-btn" data-action="${USERS_ACTION_LOGOUT_USER}" data-user-id="${userIdAttr}" ${renderLabelAttributes(logoutLabel)}>${logoutLabel}</button>` : '';
    const passwordLabel = i18n.t('settings.users.passwordButton');
    const passwordButton = context.canChangePassword(userId) ? `<button type="button" class="ui-button ui-button--sm ui-variant-neutral" data-action="${USERS_ACTION_CHANGE_PASSWORD}" data-user-id="${userIdAttr}" ${renderLabelAttributes(passwordLabel)}>${passwordLabel}</button>` : '';
    const renameLabel = i18n.t('settings.users.rename.button');
    const renameButton = isCurrentUser(userId) || context.showAdminActions ? `<button type="button" class="ui-button ui-button--sm ui-variant-neutral" data-action="${USERS_ACTION_RENAME}" data-user-id="${userIdAttr}" ${renderLabelAttributes(renameLabel)}>${renameLabel}</button>` : '';
    const changeWorkspacePathLabel = i18n.t('settings.users.changeWorkspacePath');
    const workspaceButton = context.showAdminActions ? `<button type="button" class="ui-button ui-button--sm ui-variant-neutral" data-action="${USERS_ACTION_CHANGE_WORKSPACE_PATH}" data-user-id="${userIdAttr}" ${renderLabelAttributes(changeWorkspacePathLabel)}>${changeWorkspacePathLabel}</button>` : '';
    const deleteLabel = i18n.t('settings.users.deleteButton');

    const changeRoleDisabled = shouldDisableChangeRole(userId);

    const deleteDisabled = shouldDisableDelete(userId);
    const deleteTitle = deleteDisabled ? i18n.t('settings.users.lastUserWarning') : deleteLabel;
    const deleteLabelAttr = escapeAttribute(deleteLabel);
    const deleteTitleAttr = escapeAttribute(deleteTitle);
    const deleteAttrs = renderControlDisabledAttributes(deleteDisabled);

    const roleBadgeClass = buildRoleBadgeClass(isAdmin);
    const roleBadgeText = buildUserRoleBadgeText(isAdmin);
    const idLabel = sanitizeHtml(i18n.t('settings.users.labels.idValue', { id: userId }));
    const workspacePathLabel = sanitizeHtml(
        i18n.t('settings.users.labels.workspacePathValue', {
            folder: user.workspacePathResolved,
            default: isDefaultWorkspacePath ? i18n.t('settings.users.labels.defaultSuffix') : ''
        })
    );
    const roleSelect = context.showRoleSelect ? buildRoleSelect({ userId, role, shouldDisableUserRole: changeRoleDisabled, disableRoleSelect: deleteDisabled, disabledTitle: deleteTitle, sanitizeHtml }) : '';

    const deleteButton = context.showAdminActions ? `<button type="button" class="ui-button ui-button--sm ui-variant-danger delete-user-btn" data-action="${USERS_ACTION_DELETE_USER}" data-user-id="${userIdAttr}" data-username="${usernameAttr}" aria-label="${deleteLabelAttr}" data-tooltip="${deleteTitleAttr}"${deleteAttrs}>${deleteLabel}</button>` : '';
    return `<div class="settings-record-item settings-record-item--user" data-user-id="${userIdAttr}"><div class="settings-record-info"><div class="settings-record-header"><span class="settings-record-label">${sanitizedUsername}</span><span class="settings-record-id-label">${idLabel}</span><span class="settings-record-badge user-role-badge ${roleBadgeClass}">${roleBadgeText}</span></div><div class="settings-record-meta"><span>${workspacePathLabel}</span></div></div><div class="settings-record-actions">${roleSelect}${workspaceButton}${renameButton}${passwordButton}${logoutButton}${deleteButton}</div></div>`;
};

const renderUsersSection = (context: UsersManagerRenderContext): string => {
    const addUserLabel = i18n.t('settings.users.addUserButton');
    const addUserBtn = context.canAdministerUsers ? renderSettingsTitlebarAddButton({ id: 'add-user-btn', action: USERS_ACTION_ADD_USER, label: addUserLabel }) : '';
    const refreshBtn = renderSettingsTitlebarRefreshButton({ id: 'users-refresh-btn', action: USERS_ACTION_REFRESH, label: i18n.t('settings.users.refreshButton') });
    const showRoleSelect = context.canAdministerUsers && context.users.length > 1;
    const userItems = context.users.map((user) => buildUserItem({ user, sanitizeHtml: context.sanitizeHtml, isCurrentUser: context.isCurrentUser, canChangePassword: context.canChangePassword, shouldDisableChangeRole: context.shouldDisableChangeRole, shouldDisableDelete: context.shouldDisableDelete, showAdminActions: context.canAdministerUsers, showRoleSelect }));

    return renderSection({
        title: i18n.t('settings.users.sectionTitle'),
        description: i18n.t('settings.users.sectionDescription'),
        className: 'settings-section--users',
        trailing: `${refreshBtn}${addUserBtn}`,
        content: `${renderSettingsCapabilityNotice(context.availability)}${renderSettingsSubgroup({
            title: i18n.t('settings.users.list.title'),
            description: i18n.t('settings.users.list.description'),
            content: renderSettingsRecordList({
                id: 'users-list',
                items: userItems,
                empty: renderEmptyState({ title: i18n.t('settings.users.list.empty'), className: 'ui-empty-state--simple' }).html,
                className: 'settings-record-list--users'
            })
        })}${renderSettingsSubgroup({
            title: i18n.t('settings.users.sessions.title'),
            description: i18n.t('settings.users.sessions.description'),
            attributes: { id: 'webui-sessions-subgroup' },
            content: renderSettingsRecordList({ id: 'webui-sessions-list', items: [], empty: renderSessionsContent(null), className: 'settings-record-list--sessions' })
        })}${context.productSection}`
    });
};

export { renderUsersSection };
