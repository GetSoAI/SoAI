/* SoAI - Settings page users manager constants [frontend/assets/ts/pages/settings/controllers/usersmanager/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

const USERS_ACTION_ADD_USER = 'users-add-user';
const USERS_ACTION_REFRESH = 'users-refresh';
const USERS_ACTION_SELECT_ROLE = 'users-select-role';
const USERS_ACTION_CHANGE_WORKSPACE_PATH = 'users-change-workspace-path';
const USERS_ACTION_CHANGE_PASSWORD = 'users-change-password';
const USERS_ACTION_RENAME = 'users-rename';
const USERS_ACTION_DELETE_USER = 'users-delete-user';
const USERS_ACTION_LOGOUT_USER = 'users-logout-user';

type UsersActionId = typeof USERS_ACTION_ADD_USER | typeof USERS_ACTION_REFRESH | typeof USERS_ACTION_CHANGE_WORKSPACE_PATH | typeof USERS_ACTION_CHANGE_PASSWORD | typeof USERS_ACTION_RENAME | typeof USERS_ACTION_DELETE_USER | typeof USERS_ACTION_LOGOUT_USER;
type UsersRoleSelectActionId = typeof USERS_ACTION_SELECT_ROLE;

const { guard: isUsersActionId } = createActionIdSet(USERS_ACTION_ADD_USER, USERS_ACTION_REFRESH, USERS_ACTION_CHANGE_WORKSPACE_PATH, USERS_ACTION_CHANGE_PASSWORD, USERS_ACTION_RENAME, USERS_ACTION_DELETE_USER, USERS_ACTION_LOGOUT_USER);
const { guard: isUsersRoleSelectActionId } = createActionIdSet(USERS_ACTION_SELECT_ROLE);

export { USERS_ACTION_ADD_USER, USERS_ACTION_CHANGE_PASSWORD, USERS_ACTION_CHANGE_WORKSPACE_PATH, USERS_ACTION_DELETE_USER, USERS_ACTION_LOGOUT_USER, USERS_ACTION_REFRESH, USERS_ACTION_RENAME, USERS_ACTION_SELECT_ROLE, type UsersActionId, type UsersRoleSelectActionId, isUsersActionId, isUsersRoleSelectActionId };
