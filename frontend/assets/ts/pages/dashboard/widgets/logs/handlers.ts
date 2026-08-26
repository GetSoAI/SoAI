/* SoAI - Dashboard page handlers [frontend/assets/ts/pages/dashboard/widgets/logs/handlers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { DASHBOARD_ACTION_LOGS_AUTOSCROLL_TOGGLE, DASHBOARD_ACTION_LOGS_SIZE_DECREASE, DASHBOARD_ACTION_LOGS_SIZE_INCREASE, type DashboardActionId } from '@pages/dashboard/actions.ts';
import { formatLogsAutoScrollLabel } from '@pages/dashboard/widgets/logs/LogsLabelsWidget.ts';
import { DashboardLogsState } from '@pages/dashboard/widgets/logs/state.ts';
import type { DashboardLogsView } from '@pages/dashboard/widgets/logs/view.ts';

interface DashboardLogsActionDependencies {
    state: DashboardLogsState;
    view: DashboardLogsView;
}

const applyDashboardLogsAction = (actionId: DashboardActionId, target: HTMLElement | null, dependencies: DashboardLogsActionDependencies): void => {
    if (actionId === DASHBOARD_ACTION_LOGS_SIZE_DECREASE) {
        const scale = dependencies.state.adjustFont(-0.1);
        dependencies.view.applyFontScale(scale);
        return;
    }
    if (actionId === DASHBOARD_ACTION_LOGS_SIZE_INCREASE) {
        const scale = dependencies.state.adjustFont(0.1);
        dependencies.view.applyFontScale(scale);
        return;
    }
    if (actionId === DASHBOARD_ACTION_LOGS_AUTOSCROLL_TOGGLE) {
        const autoScroll = dependencies.state.toggleAutoScroll();
        const button = target instanceof HTMLButtonElement ? target : target?.closest('button');
        if (button) {
            const label = formatLogsAutoScrollLabel(autoScroll);
            button.setAttribute('aria-pressed', String(autoScroll));
            button.setAttribute('aria-label', label);
            setTooltipText(button, label);
            button.textContent = label;
        }
        if (autoScroll) {
            dependencies.view.scrollToEnd();
        }
    }
};

export { applyDashboardLogsAction };
