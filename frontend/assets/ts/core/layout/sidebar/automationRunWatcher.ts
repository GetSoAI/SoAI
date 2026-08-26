/* SoAI - Shared layout automation run watcher [frontend/assets/ts/core/layout/sidebar/automationRunWatcher.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireAutomationRunActivitySubscribe } from '@core/automation/serviceAccess.ts';
import type { SidebarLinkIndicatorController } from '@core/layout/sidebar/linkIndicator.ts';

const subscribeAutomationRunWatcher = (indicator: SidebarLinkIndicatorController): (() => void) => {
    const activity = requireAutomationRunActivitySubscribe();
    return activity.subscribe((snapshot) => {
        indicator.setVisible(snapshot.hasRunning);
    });
};

export { subscribeAutomationRunWatcher };
