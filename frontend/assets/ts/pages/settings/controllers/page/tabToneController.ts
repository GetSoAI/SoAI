/* SoAI - Settings page tab tone controller [frontend/assets/ts/pages/settings/controllers/page/tabToneController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SettingsRuntimeContext } from '@pages/settings/controllers/page/contracts.ts';
import type { SettingsPageState } from '@pages/settings/controllers/page/state.ts';

const TAB_TONE_CLASSES: readonly string[] = Object.freeze(['tabs-tab--tone-green', 'tabs-tab--tone-orange', 'tabs-tab--tone-red', 'tabs-tab--tone-blue']);

const resetTabTone = (page: SettingsRuntimeContext, tab: Element): void => {
    TAB_TONE_CLASSES.forEach((className) => {
        page.owners.pageDom.removeClass(tab, className);
    });
};

const applyAdvancedTabTones = (page: SettingsRuntimeContext, state: SettingsPageState): void => {
    state.advancedTabs.forEach((tab) => {
        const element = page.owners.pageDom.optional(`#${tab.id}-tab`);
        if (!element) {
            return;
        }
        page.owners.pageDom.updateAttribute(element, 'data-advanced', 'true');
        page.owners.pageDom.addClass(element, 'tabs-tab--tone-orange');
    });
};

const applySettingsTabTones = (page: SettingsRuntimeContext, state: SettingsPageState): void => {
    page.owners.pageDom.query('.tabs-tab').forEach((tab) => {
        resetTabTone(page, tab);
    });
    const resetTab = page.owners.pageDom.optional('#reset-tab');
    if (resetTab) {
        page.owners.pageDom.addClass(resetTab, 'tabs-tab--tone-red');
    }
    applyAdvancedTabTones(page, state);
};

export { applySettingsTabTones };
