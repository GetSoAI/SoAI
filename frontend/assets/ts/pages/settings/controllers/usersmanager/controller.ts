/* SoAI - Settings page control layer users manager controller [frontend/assets/ts/pages/settings/controllers/usersmanager/controller.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { APIError } from '@core/apiError.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { publishTerminalAccessPolicyInvalidation } from '@core/routing/router/terminalAccessPolicy.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { executeConfirmedButtonAction } from '@pages/settings/controllers/page/confirmedactionexecution/service.ts';
import { parseUserRole } from '@pages/settings/controllers/usersmanager/guards.ts';
import { openUserWorkspacePathPicker } from '@pages/settings/controllers/usersmanager/workspacePathPickerModal.ts';
import type { UsersManagerInteractionContext } from '@pages/settings/controllers/usersmanager/types.ts';

const performChangeUserRoleAction = async (context: UsersManagerInteractionContext & { userId: string; targetRole: string }): Promise<void> => {
    const { host, userId, targetRole, getUserById, shouldPreventAdminDemotion, reloadUsers } = context;
    const user = getUserById(userId);
    if (!user) {
        return;
    }

    const newRole = parseUserRole(targetRole);
    if (user.isAdmin === (newRole === 'admin')) {
        return;
    }

    if (newRole === 'user' && shouldPreventAdminDemotion(userId)) {
        host.notifications.feedback.show(i18n.t('settings.users.lastAdminWarning'), 'warning');
        return;
    }

    await host.execution.confirmAndExecute(
        'settings:changeUserRole',
        {
            title: i18n.t('settings.users.changeRoleModal.title'),
            message: i18n.t('settings.users.changeRoleModal.message', { role: newRole })
        },
        () =>
            host.execution.runPageTask('settings.changeUserRole', () => host.api.updateUser(user.id, newRole === 'admin'), {
                displayName: i18n.t('settings.users.changeRoleModal.title')
            }),
        i18n.t('settings.notifications.userRoleUpdateSuccess'),
        async () => {
            publishTerminalAccessPolicyInvalidation();
            await reloadUsers();
        },
        null
    );
};

const performLogoutUserAction = async (context: UsersManagerInteractionContext & { button: HTMLButtonElement }): Promise<void> => {
    const { host, button, getUserById, isCurrentUser } = context;
    const userId = requireTrimmedDataAttribute(button, 'user-id', 'Users action element');

    const user = getUserById(userId);
    if (!user || !isCurrentUser(user)) {
        return;
    }

    await executeConfirmedButtonAction({
        host: host.execution,
        button,
        boundaryName: 'settings:logoutCurrentUser',
        confirmOptions: {
            title: i18n.t('header.menu.logout'),
            message: i18n.t('header.confirmations.logoutMessage'),
            confirmText: i18n.t('header.menu.logout'),
            cancelText: i18n.t('common.cancel'),
            variant: 'warning'
        },
        action: async (): Promise<null> => {
            await host.api.logout();
            return null;
        }
    });
};

const performDeleteUserAction = async (context: UsersManagerInteractionContext & { userId: string; username: string }): Promise<void> => {
    const { host, userId, username, shouldPreventUserDeletion, reloadUsers, getUserById } = context;
    const user = getUserById(userId);
    if (!user) return;
    if (shouldPreventUserDeletion(userId)) {
        host.notifications.feedback.show(i18n.t('settings.users.lastUserWarning'), 'warning');
        return;
    }

    await host.execution.confirmAndExecute(
        'settings:deleteUser',
        {
            title: i18n.t('settings.users.deleteUserModal.title'),
            message: i18n.t('settings.users.deleteUserModal.message', { username }),
            confirmText: i18n.t('settings.users.deleteButton'),
            cancelText: i18n.t('common.cancel'),
            variant: 'danger'
        },
        () =>
            host.execution.runPageTask('settings.deleteUser', () => host.api.deleteUser(user.id), {
                displayName: i18n.t('settings.users.deleteUserModal.title')
            }),
        i18n.t('settings.notifications.userDeleteSuccess'),
        async () => {
            publishTerminalAccessPolicyInvalidation();
            await reloadUsers();
        },
        null
    );
};

const performChangeUserWorkspacePathAction = async (context: UsersManagerInteractionContext & { userId: string }): Promise<void> => {
    const { host, userId, getUserById, reloadUsers } = context;
    const user = getUserById(userId);
    if (!user) {
        return;
    }
    const nextWorkspacePath = await openUserWorkspacePathPicker(host.api, user);
    if (nextWorkspacePath === undefined) {
        return;
    }
    await host.execution.confirmAndExecute(
        'settings:changeUserWorkspacePath',
        null,
        async () => {
            await host.execution.runPageTask('settings.updateUserWorkspacePath', () => host.api.updateUserWorkspacePath(user.id, nextWorkspacePath), {
                displayName: i18n.t('settings.users.changeWorkspacePathModal.title')
            });
            await reloadUsers();
            return null;
        },
        i18n.t('settings.notifications.userWorkspacePathUpdateSuccessRevoked'),
        null,
        null
    );
};

const performChangeUserPasswordAction = async (context: UsersManagerInteractionContext & { button: HTMLButtonElement; userId: string }): Promise<void> => {
    const { host, button, userId, getUserById, isCurrentUser, applyUserResult } = context;
    const user = getUserById(userId);
    if (!user) {
        return;
    }
    const canChangePassword = host.state.canAdministerUsers() || isCurrentUser(user);
    if (!canChangePassword) {
        host.notifications.feedback.show(i18n.t('settings.users.passwordModal.notAllowed'), 'warning');
        return;
    }
    await host.execution.withButtonDisabled(button, async () => {
        const fieldLabels = {
            current: i18n.t('settings.users.passwordModal.fields.current'),
            new: i18n.t('settings.users.passwordModal.fields.new'),
            confirm: i18n.t('settings.users.passwordModal.fields.confirm')
        };
        const validationMessages = {
            currentRequired: i18n.t('settings.users.passwordModal.validation.currentRequired'),
            newRequired: i18n.t('settings.users.passwordModal.validation.newRequired'),
            tooLong: i18n.t('settings.users.passwordModal.validation.tooLong'),
            tooShort: i18n.t('settings.users.passwordModal.validation.tooShort'),
            confirmMismatch: i18n.t('settings.users.passwordModal.validation.confirmMismatch'),
            updateFailed: i18n.t('settings.users.passwordModal.updateFailed')
        };
        const completed = await requireDialogsService().showPasswordChange({
            title: i18n.t('settings.users.passwordModal.title'),
            message: i18n.t('settings.users.passwordModal.message', { username: user.username }),
            fieldLabels,
            validationMessages,
            submitText: i18n.t('settings.users.passwordModal.submitButton'),
            onSubmit: async (values) => {
                try {
                    const result = isCurrentUser(user) ? await host.api.changeOwnPassword(values.operationId, values.currentPassword, values.newPassword) : await host.api.changeUserPassword(user.id, values.operationId, values.currentPassword, values.newPassword, context.signal);
                    applyUserResult(result.user);
                    return null;
                } catch (error) {
                    const ensuredError = ensureError(error);
                    if (ensuredError instanceof APIError) {
                        switch (ensuredError.code) {
                            case 'incorrect_current_password':
                                return { message: i18n.t('settings.users.passwordModal.incorrectCurrent'), retainOperationId: false };
                            case 'rate_limit_exceeded':
                                return { message: i18n.t('settings.users.passwordModal.retryLater'), retainOperationId: false };
                            case 'identity_mutation_result_unknown':
                                return { message: i18n.t('settings.users.passwordModal.unknown'), retainOperationId: true };
                            case 'operation_id_conflict':
                            case 'user_state_conflict':
                            case 'identity_mutation_deadline_exceeded':
                            case 'identity_mutation_cancelled':
                            case 'identity_mutation_not_committed':
                            case 'session_rotation_window_unavailable':
                                return { message: i18n.t('settings.users.passwordModal.conflict'), retainOperationId: false };
                        }
                    }
                    host.notifications.feedback.handle(ensuredError, i18n.t('settings.users.passwordModal.title'));
                    errorHandler.debug('SettingsUsers', 'Password update returned an unclassified failure', ensuredError);
                    return { message: validationMessages.updateFailed, retainOperationId: false };
                }
            }
        });
        if (!completed) {
            return;
        }
        host.notifications.feedback.show(i18n.t('settings.notifications.userPasswordUpdateSuccess'), 'success');
    });
};

const resolveRenameError = (error: Error): { message: string; retainOperationId: boolean } => {
    if (!(error instanceof APIError)) return { message: i18n.t('settings.users.rename.errors.failed'), retainOperationId: false };
    switch (error.code) {
        case 'incorrect_current_password':
            return { message: i18n.t('settings.users.rename.errors.incorrectPassword'), retainOperationId: false };
        case 'username_conflict':
            return { message: i18n.t('settings.users.rename.errors.conflict'), retainOperationId: false };
        case 'username_unchanged':
            return { message: i18n.t('settings.users.rename.errors.unchanged'), retainOperationId: false };
        case 'operation_id_conflict':
            return { message: i18n.t('settings.users.rename.errors.operationConflict'), retainOperationId: false };
        case 'user_state_conflict':
            return { message: i18n.t('settings.users.rename.errors.stateConflict'), retainOperationId: false };
        case 'identity_mutation_result_unknown':
            return { message: i18n.t('settings.users.rename.errors.unknown'), retainOperationId: true };
        case 'identity_mutation_deadline_exceeded':
        case 'identity_mutation_cancelled':
            return { message: i18n.t('settings.users.rename.errors.deadline'), retainOperationId: false };
        default:
            return { message: i18n.t('settings.users.rename.errors.failed'), retainOperationId: false };
    }
};

const performRenameUserAction = async (context: UsersManagerInteractionContext & { button: HTMLButtonElement; userId: string }): Promise<void> => {
    const { host, button, userId, getUserById, isCurrentUser, applyUserResult } = context;
    const user = getUserById(userId);
    if (!user || (!isCurrentUser(user) && !host.state.canAdministerUsers())) return;
    await host.execution.withButtonDisabled(button, async () => {
        const completed = await requireDialogsService().showUsernameRename({
            title: i18n.t('settings.users.rename.title'),
            message: i18n.t('settings.users.rename.notice'),
            usernameLabel: i18n.t('settings.users.rename.usernameLabel'),
            passwordLabel: i18n.t('settings.users.rename.passwordLabel'),
            currentUsername: user.username,
            submitText: i18n.t('settings.users.rename.submit'),
            invalidUsername: i18n.t('settings.users.rename.errors.invalid'),
            unchangedUsername: i18n.t('settings.users.rename.errors.unchanged'),
            passwordRequired: i18n.t('settings.users.rename.errors.passwordRequired'),
            updateFailed: i18n.t('settings.users.rename.errors.failed'),
            onSubmit: async (values) => {
                try {
                    const result = isCurrentUser(user) ? await host.api.renameOwnUsername(values.operationId, values.newUsername, values.currentPassword) : await host.api.renameUser(user.id, values.operationId, values.newUsername, values.currentPassword, context.signal);
                    applyUserResult(result.user);
                    return null;
                } catch (error) {
                    return resolveRenameError(ensureError(error));
                }
            }
        });
        if (completed) host.notifications.feedback.show(i18n.t('settings.users.rename.success'), 'success');
    });
};

export { performChangeUserPasswordAction, performChangeUserRoleAction, performChangeUserWorkspacePathAction, performLogoutUserAction, performDeleteUserAction, performRenameUserAction };
