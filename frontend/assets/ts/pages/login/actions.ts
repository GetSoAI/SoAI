/* SoAI - Login page actions [frontend/assets/ts/pages/login/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

const LOGIN_ACTION_SUBMIT = 'login:submit';
const LOGIN_ACTION_OPEN_DOCUMENTATION = 'login:openDocumentation';

export type LoginActionId = typeof LOGIN_ACTION_SUBMIT | typeof LOGIN_ACTION_OPEN_DOCUMENTATION;

const { guard: isLoginActionId } = createActionIdSet(LOGIN_ACTION_SUBMIT, LOGIN_ACTION_OPEN_DOCUMENTATION);

export { LOGIN_ACTION_SUBMIT, LOGIN_ACTION_OPEN_DOCUMENTATION, isLoginActionId };
