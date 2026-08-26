/* SoAI - Settings page DOM contracts [frontend/assets/ts/pages/settings/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { assertElementDataAction } from '@core/dom/dataAction.ts';
import { narrowButton, optionalButton } from '@core/dom/narrowElement.ts';
import { UI_IDS } from '@features/settings/public.ts';
import { SETTINGS_ACTION_SAVE, SETTINGS_ACTION_TOGGLE_ADVANCED_MODE } from '@pages/settings/actions.ts';
import type { SettingsUi } from '@pages/settings/types.ts';

export const requireSettingsUi = (dependencies: { requireHTMLElement: (selector: string, context?: ParentNode) => HTMLElement; optionalHTMLElement: (selector: string, context?: ParentNode) => HTMLElement | null }): SettingsUi => {
    const root = dependencies.requireHTMLElement('[data-section="settings"]');

    const tabsContainer = dependencies.requireHTMLElement(`#${UI_IDS.TAB_CONTAINER}`, root);
    const content = dependencies.requireHTMLElement(`#${UI_IDS.CONTENT}`, root);
    const searchContainer = dependencies.requireHTMLElement(`#${UI_IDS.SEARCH_CONTAINER}`, root);
    const saveButton = narrowButton(dependencies.requireHTMLElement(`#${UI_IDS.SAVE_BUTTON}`, root), 'Save button');
    assertElementDataAction(saveButton, SETTINGS_ACTION_SAVE, 'Save button');
    const pageActionRoot = saveButton.closest('.page-header-panel');
    if (!(pageActionRoot instanceof HTMLElement)) {
        throw new Error('Settings page action root is missing');
    }

    const advancedModeToggleButton = optionalButton(dependencies.optionalHTMLElement(`#${UI_IDS.ADVANCED_TOGGLE_BTN}`, root), 'Advanced mode toggle button');
    if (advancedModeToggleButton) {
        assertElementDataAction(advancedModeToggleButton, SETTINGS_ACTION_TOGGLE_ADVANCED_MODE, 'Advanced mode toggle button');
    }

    return {
        root,
        pageActionRoot,
        tabsContainer,
        content,
        searchContainer,
        saveButton,
        advancedModeToggleButton
    };
};

export const optionalSettingsRoot = (dependencies: { optionalHTMLElement: (selector: string, context?: ParentNode) => HTMLElement | null }): HTMLElement | null => {
    const root = dependencies.optionalHTMLElement('[data-section="settings"]');
    if (!root) {
        return null;
    }
    return root;
};
