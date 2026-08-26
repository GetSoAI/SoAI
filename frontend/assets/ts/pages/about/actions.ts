/* SoAI - About page actions [frontend/assets/ts/pages/about/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

export const ABOUT_ACTION_SHOW_LICENSE = 'about.showLicense';
export const ABOUT_ACTION_SHOW_CREDITS = 'about.showCredits';

export type AboutActionId = typeof ABOUT_ACTION_SHOW_LICENSE | typeof ABOUT_ACTION_SHOW_CREDITS;

const { guard: isAboutActionId } = createActionIdSet(ABOUT_ACTION_SHOW_LICENSE, ABOUT_ACTION_SHOW_CREDITS);

export { isAboutActionId };
