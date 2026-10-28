/* SoAI - Updates page actions [frontend/assets/ts/pages/updates/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

export const UPDATES_ACTION_CHECK = 'updates.check';
export const UPDATES_ACTION_INSTALL = 'updates.install';
export const UPDATES_ACTION_OPEN_PLUGINS = 'updates.openPlugins';

export type UpdatesActionId = typeof UPDATES_ACTION_CHECK | typeof UPDATES_ACTION_INSTALL | typeof UPDATES_ACTION_OPEN_PLUGINS;

const { guard: isUpdatesActionId } = createActionIdSet(UPDATES_ACTION_CHECK, UPDATES_ACTION_INSTALL, UPDATES_ACTION_OPEN_PLUGINS);

export { isUpdatesActionId };
