/* SoAI - Settings page users manager events [frontend/assets/ts/pages/settings/controllers/usersmanager/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { narrowButton, narrowSelect } from '@core/dom/narrowElement.ts';
import { i18n } from '@core/i18n/index.ts';
import { isUsersActionId, isUsersRoleSelectActionId, USERS_ACTION_ADD_USER, USERS_ACTION_CHANGE_PASSWORD, USERS_ACTION_CHANGE_WORKSPACE_PATH, USERS_ACTION_DELETE_USER, USERS_ACTION_LOGOUT_USER, USERS_ACTION_REFRESH, USERS_ACTION_RENAME, USERS_ACTION_SELECT_ROLE, type UsersActionId, type UsersRoleSelectActionId } from '@pages/settings/controllers/usersmanager/constants.ts';
import { performChangeUserPasswordAction, performChangeUserWorkspacePathAction, performChangeUserRoleAction, performDeleteUserAction, performLogoutUserAction, performRenameUserAction } from '@pages/settings/controllers/usersmanager/controller.ts';
import { performAddUserAction } from '@pages/settings/controllers/usersmanager/userCreationController.ts';
import type { UsersManagerInteractionContext } from '@pages/settings/controllers/usersmanager/types.ts';

type UsersManagerClickContext = UsersManagerInteractionContext & {
    reloadUsers: () => Promise<void>;
};

const executeUsersManagerAction = async (action: UsersActionId, actionElement: HTMLElement, context: UsersManagerClickContext): Promise<void> => {
    const button = narrowButton(actionElement, 'Users action element');
    switch (action) {
        case USERS_ACTION_ADD_USER: {
            await performAddUserAction({ host: context.host, reloadUsers: context.reloadUsers });
            return;
        }
        case USERS_ACTION_REFRESH: {
            await context.reloadUsers();
            context.host.notifications.feedback.show(i18n.t('common.notifications.refreshCompleted'), 'refresh');
            return;
        }
        case USERS_ACTION_CHANGE_WORKSPACE_PATH: {
            const userId = requireTrimmedDataAttribute(button, 'user-id', 'Users action element');
            await performChangeUserWorkspacePathAction({
                ...context,
                userId
            });
            return;
        }
        case USERS_ACTION_CHANGE_PASSWORD: {
            const userId = requireTrimmedDataAttribute(button, 'user-id', 'Users action element');
            await performChangeUserPasswordAction({
                ...context,
                button,
                userId
            });
            return;
        }
        case USERS_ACTION_RENAME: {
            const userId = requireTrimmedDataAttribute(button, 'user-id', 'Users action element');
            await performRenameUserAction({ ...context, button, userId });
            return;
        }
        case USERS_ACTION_DELETE_USER: {
            const userId = requireTrimmedDataAttribute(button, 'user-id', 'Users action element');
            const username = requireTrimmedDataAttribute(button, 'username', 'Users action element');
            await performDeleteUserAction({
                ...context,
                userId,
                username
            });
            return;
        }
        case USERS_ACTION_LOGOUT_USER: {
            await performLogoutUserAction({
                ...context,
                button
            });
            return;
        }
        default: {
            const exhaustive: never = action;
            throw new Error(`Unhandled users action: ${exhaustive}`);
        }
    }
};

const executeUsersRoleSelectAction = async (action: UsersRoleSelectActionId, actionElement: HTMLElement, context: UsersManagerClickContext): Promise<void> => {
    const select = narrowSelect(actionElement, 'Users role select');
    switch (action) {
        case USERS_ACTION_SELECT_ROLE: {
            const userId = requireTrimmedDataAttribute(select, 'user-id', 'Users role select');
            const targetRole = select.value;
            select.value = '';
            await performChangeUserRoleAction({
                ...context,
                userId,
                targetRole
            });
            return;
        }
        default: {
            const exhaustive: never = action;
            throw new Error(`Unhandled users role select action: ${exhaustive}`);
        }
    }
};

export { executeUsersManagerAction, executeUsersRoleSelectAction, isUsersActionId, isUsersRoleSelectActionId };
