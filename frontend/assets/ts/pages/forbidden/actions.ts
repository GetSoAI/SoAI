/* SoAI - Forbidden page actions [frontend/assets/ts/pages/forbidden/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

export const FORBIDDEN_ACTION_GO_DEFAULT_ROUTE = 'forbidden.goDefaultRoute';
export const FORBIDDEN_ACTION_GO_BACK = 'forbidden.goBack';

export type ForbiddenActionId = typeof FORBIDDEN_ACTION_GO_DEFAULT_ROUTE | typeof FORBIDDEN_ACTION_GO_BACK;

const { guard: isForbiddenActionId } = createActionIdSet(FORBIDDEN_ACTION_GO_DEFAULT_ROUTE, FORBIDDEN_ACTION_GO_BACK);

export { isForbiddenActionId };
