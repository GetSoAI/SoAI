/* SoAI - Automation page initial selection controller [frontend/assets/ts/pages/automation/controllers/initialSelectionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveAutomationZoneByKey } from '@pages/automation/contracts/zoneKey.ts';
import type { AutomationZone } from '@features/automation/public.ts';
import type { AutomationInitialSelection, AutomationPageState } from '@pages/automation/types.ts';

const applyAutomationInitialSelection = (state: AutomationPageState, selection: AutomationInitialSelection | null): AutomationPageState => {
    if (selection == null) {
        return state;
    }
    return {
        ...state,
        ...selection
    };
};

const isAutomationInitialSelectionVisible = (zones: readonly AutomationZone[], selection: AutomationInitialSelection | null): boolean => {
    if (selection == null) {
        return true;
    }
    return resolveAutomationZoneByKey(zones, selection.selectedZoneKey) !== null;
};

export { applyAutomationInitialSelection, isAutomationInitialSelectionVisible };
