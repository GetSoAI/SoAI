/* SoAI - Help page actions [frontend/assets/ts/pages/help/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

export const HELP_ACTION_NAVIGATE_ABOUT = 'help.navigateAbout';

export type HelpActionId = typeof HELP_ACTION_NAVIGATE_ABOUT;

const { guard: isHelpActionId } = createActionIdSet(HELP_ACTION_NAVIGATE_ABOUT);

export { isHelpActionId };
