/* SoAI - Settings page action handlers [frontend/assets/ts/pages/settings/controllers/settingsActionHandlers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SETTINGS_ACTION_REFRESH_OCR, SETTINGS_ACTION_SAVE, SETTINGS_ACTION_TOGGLE_ADVANCED_MODE, type SettingsActionId } from '@pages/settings/actions.ts';

interface SettingsActionHandlersHost {
    refreshOcr(): void;
    save(): void;
    toggleAdvancedMode(event: Event, element: HTMLElement): void;
}

const createSettingsActionHandlers = (host: SettingsActionHandlersHost): Record<SettingsActionId, (event: Event, element: HTMLElement) => void> => {
    return {
        [SETTINGS_ACTION_REFRESH_OCR]: () => host.refreshOcr(),
        [SETTINGS_ACTION_SAVE]: () => host.save(),
        [SETTINGS_ACTION_TOGGLE_ADVANCED_MODE]: (event: Event, element: HTMLElement) => host.toggleAdvancedMode(event, element)
    };
};

export { createSettingsActionHandlers };
export type { SettingsActionHandlersHost };
