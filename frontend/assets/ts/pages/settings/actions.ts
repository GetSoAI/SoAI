/* SoAI - Settings page actions [frontend/assets/ts/pages/settings/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

export const SETTINGS_ACTION_SAVE = 'settings-save';
export const SETTINGS_ACTION_TOGGLE_ADVANCED_MODE = 'settings-toggle-advanced-mode';

export type SettingsActionId = typeof SETTINGS_ACTION_SAVE | typeof SETTINGS_ACTION_TOGGLE_ADVANCED_MODE;

const { guard: isSettingsActionId } = createActionIdSet(SETTINGS_ACTION_SAVE, SETTINGS_ACTION_TOGGLE_ADVANCED_MODE);

export { isSettingsActionId };
