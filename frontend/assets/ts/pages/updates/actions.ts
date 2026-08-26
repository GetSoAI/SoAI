/* SoAI - Updates page actions [frontend/assets/ts/pages/updates/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

export const UPDATES_ACTION_CHECK = 'updates.check';
export const UPDATES_ACTION_INSTALL = 'updates.install';

export type UpdatesActionId = typeof UPDATES_ACTION_CHECK | typeof UPDATES_ACTION_INSTALL;

const { guard: isUpdatesActionId } = createActionIdSet(UPDATES_ACTION_CHECK, UPDATES_ACTION_INSTALL);

export { isUpdatesActionId };
