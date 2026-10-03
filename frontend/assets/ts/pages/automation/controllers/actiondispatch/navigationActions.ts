/* SoAI - Automation page navigation actions [frontend/assets/ts/pages/automation/controllers/actiondispatch/navigationActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAutomationViewMode } from '@core/automation/guards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import type { AutomationPageActionDispatcherHost } from '@pages/automation/controllers/actiondispatch/AutomationPageActionDispatcherHost.ts';
import { buildAutomationBufferedWindowSignature } from '@pages/automation/controllers/automationWindow.ts';
import { AutomationUserNotifiedError } from '@pages/automation/controllers/AutomationUserNotifiedError.ts';
import { applyViewMode, selectDayAndZoom } from '@pages/automation/controllers/stateTransitions.ts';
import { navigateToday } from '@pages/automation/controllers/todayNavigation.ts';
import type { AutomationViewMode } from '@pages/automation/types.ts';

const runRefreshOrNotify = async (host: AutomationPageActionDispatcherHost, refresh: () => Promise<void>, dependencies: { logSource: string; logMessage: string }): Promise<void> => {
    try {
        await refresh();
    } catch (error) {
        const runtimeError = ensureError(error);
        host.controllers.reportRefreshFailure(runtimeError);
        errorHandler.warn(dependencies.logSource, dependencies.logMessage, runtimeError);
        throw new AutomationUserNotifiedError(runtimeError);
    }
};

const refreshAutomationDataOrNotify = async (host: AutomationPageActionDispatcherHost, dependencies: { logSource: string; logMessage: string }): Promise<void> => {
    await runRefreshOrNotify(host, () => host.state.refreshData(), dependencies);
};

const refreshWithNotification = async (host: AutomationPageActionDispatcherHost, context: string): Promise<void> => {
    await refreshAutomationDataOrNotify(host, { logSource: 'AutomationNavigationActions', logMessage: context });
};

const handleSelectDay = (host: AutomationPageActionDispatcherHost, iso: string): void => {
    const trimmed = iso.trim();
    if (!trimmed) {
        throw new Error('Automation day selection requires data-date');
    }
    const nextState = selectDayAndZoom(host.state.getState(), trimmed);
    host.state.setState(nextState);
    host.state.persistPreferences();
    host.controllers.requestCenterPeriodAfterNextRender();
    host.state.stageCalendarTransition('detail-forward', buildAutomationBufferedWindowSignature(nextState));
    host.controllers.run('automation:selectDay', async () => refreshWithNotification(host, 'Refresh failed after selecting day'));
};

const resolveViewDetailLevel = (viewMode: AutomationViewMode): number => {
    if (viewMode === 'month') {
        return 0;
    }
    if (viewMode === 'week') {
        return 1;
    }
    return 2;
};

const resolveTransitionDirection = (currentViewMode: AutomationViewMode, nextViewMode: AutomationViewMode): 'detail-forward' | 'detail-backward' => {
    return resolveViewDetailLevel(nextViewMode) >= resolveViewDetailLevel(currentViewMode) ? 'detail-forward' : 'detail-backward';
};

const handleSetViewMode = (host: AutomationPageActionDispatcherHost, candidate: string): void => {
    const viewMode = candidate.trim();
    if (!isAutomationViewMode(viewMode)) {
        throw new Error('Automation view mode is invalid');
    }
    const currentState = host.state.getState();
    const currentViewMode = currentState.viewMode;
    const nextState = applyViewMode(currentState, viewMode);
    if (currentViewMode !== viewMode) {
        host.controllers.requestCenterPeriodAfterNextRender();
        host.state.stageCalendarTransition(resolveTransitionDirection(currentViewMode, viewMode), buildAutomationBufferedWindowSignature(nextState), 'slow');
    }
    host.state.setState(nextState);
    host.state.persistPreferences();
    host.controllers.run('automation:setViewMode', async () => refreshWithNotification(host, 'Refresh failed after changing view mode'));
};

const handleCycleViewMode = (host: AutomationPageActionDispatcherHost): void => {
    const viewMode = host.state.getState().viewMode;
    const next = viewMode === 'month' ? 'week' : viewMode === 'week' ? 'day' : 'month';
    handleSetViewMode(host, next);
};

const handleNavigate = (host: AutomationPageActionDispatcherHost, direction: -1 | 1): void => {
    host.controllers.run(direction === -1 ? 'automation:navigatePrevious' : 'automation:navigateNext', async () => host.controllers.animateVisiblePeriod(direction));
};

const handleNavigateToday = (host: AutomationPageActionDispatcherHost): void => {
    const state = host.state.getState();
    const result = navigateToday(state);
    if (result.shouldCloseOccurrence) {
        host.controllers.getOccurrenceModal()?.close();
    }

    if (result.stateChanged) {
        host.state.setState(result.nextState);
    }
    if (result.persistPreferences) {
        host.state.persistPreferences();
    }
    if (result.stateChanged && result.requiresRefresh) {
        host.state.stageCalendarTransition(resolveTransitionDirection(state.viewMode, result.nextState.viewMode), buildAutomationBufferedWindowSignature(result.nextState));
    }

    if (result.centerNowLine) {
        if (result.stateChanged) {
            host.controllers.requestCenterNowLineAfterNextRender();
        } else {
            host.controllers.centerNowLineNow();
            return;
        }
    } else if (result.stateChanged) {
        host.controllers.requestCenterPeriodAfterNextRender();
    }

    if (result.requiresRefresh) {
        host.controllers.run('automation:navigateToday', async () => refreshWithNotification(host, 'Refresh failed after navigating to today'));
        return;
    }
    host.state.queueRender();
};

const handleToggleRegistryOverlay = (host: AutomationPageActionDispatcherHost): void => {
    const state = host.state.getState();
    host.state.setState({ ...state, registryOverlayOpen: !state.registryOverlayOpen });
    host.state.queueRender();
};

const handleNavigateRegistryPage = (host: AutomationPageActionDispatcherHost, direction: -1 | 1): void => {
    const state = host.state.getState();
    const nextOffset = direction === -1 ? Math.max(0, state.automationRegistryOffset - state.automationRegistryLimit) : state.automationRegistryOffset + state.automationRegistryLimit;
    if (nextOffset === state.automationRegistryOffset) {
        return;
    }
    host.state.setState({ ...state, automationRegistryOffset: nextOffset });
    host.controllers.run(direction === -1 ? 'automation:registryPrevious' : 'automation:registryNext', async () => refreshWithNotification(host, direction === -1 ? 'Refresh failed after navigating to previous automation page' : 'Refresh failed after navigating to next automation page'));
};

const handleRetryPageData = (host: AutomationPageActionDispatcherHost): void => {
    host.controllers.run('automation:retryPageData', async () => runRefreshOrNotify(host, () => host.state.retryPageData(), { logSource: 'AutomationNavigationActions', logMessage: 'Retrying automation page data failed' }));
};

export { handleCycleViewMode, handleNavigate, handleNavigateRegistryPage, handleNavigateToday, handleRetryPageData, handleSelectDay, handleSetViewMode, handleToggleRegistryOverlay, refreshAutomationDataOrNotify };
