/* SoAI - Dashboard page hardware widgets effects [frontend/assets/ts/pages/dashboard/controllers/hardwareWidgetsEffects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { narrowHTMLElement } from '@core/dom/narrowElement.ts';
import { i18n } from '@core/i18n/index.ts';
import { HardwareWidgetManager } from '@features/hardware/public.ts';
import type { DashboardHardwareSectionsRenderContext } from '@pages/dashboard/controllers/contracts.ts';
import type { DashboardHardwareWidgetsManagerState } from '@pages/dashboard/controllers/state.ts';
import { renderDashboardSectionState } from '@pages/dashboard/controllers/dashboardSectionStateController.ts';

const DASHBOARD_HARDWARE_WIDGET_SIZE = Object.freeze({ WIDTH: 216, HEIGHT: 216 });

const ensureDashboardHardwareWidgetsManager = (state: DashboardHardwareWidgetsManagerState, container: HTMLElement): HardwareWidgetManager => {
    const existing = state.hardwareWidgetsManager;
    if (existing) {
        return existing;
    }
    const manager = new HardwareWidgetManager({ container, size: DASHBOARD_HARDWARE_WIDGET_SIZE });
    state.hardwareWidgetsManager = manager;
    state.hardwareWidgetsInitialized = false;
    state.hardwareWidgetsInitializePromise = null;
    state.hardwareWidgetsPendingSnapshot = null;
    return manager;
};

const destroyHardwareWidgetsManager = (state: DashboardHardwareWidgetsManagerState): void => {
    state.hardwareWidgetsInitializePromise = null;
    state.hardwareWidgetsPendingSnapshot = null;
    state.hardwareWidgetsInitialized = false;
    state.hardwareWidgetsManager?.destroy();
    state.hardwareWidgetsManager = null;
};

const renderHardwareWidgetsSection = async (
    dependencies: DashboardHardwareSectionsRenderContext & {
        widgets: DashboardHardwareWidgetsManagerState;
    }
): Promise<void> => {
    const { host, state, isDestroyed, widgets } = dependencies;
    if (isDestroyed()) {
        return;
    }

    const content = host.requireUI('hardwareWidgets-content');
    const contentElement = narrowHTMLElement(content, 'dashboard hardware widgets content');

    if (!state.hasHardware()) {
        renderDashboardSectionState(host, contentElement, 'section-loading', i18n.t('common.loading'));
        return;
    }

    const snapshotCandidate = state.getRawHardwareSnapshot();
    if (snapshotCandidate === null) {
        renderDashboardSectionState(host, contentElement, 'section-empty', i18n.t('dashboard.sections.hardwareWidgets.empty'));
        return;
    }

    widgets.hardwareWidgetsPendingSnapshot = snapshotCandidate;

    const ensureContainer = (): HTMLElement => {
        const existing = host.optionalHTMLElement('.dashboard-hardware-widgets-container', contentElement);
        if (existing) {
            return existing;
        }

        const wrapper = host.createElement('div', { className: 'dashboard-hardware-widgets-content' });
        const wrapperElement = narrowHTMLElement(wrapper, 'dashboard hardware widgets wrapper');

        const container = host.createElement('div', { className: 'hardware-widgets-container dashboard-hardware-widgets-container' });
        const containerElement = narrowHTMLElement(container, 'dashboard hardware widgets container');

        wrapperElement.appendChild(containerElement);
        host.replaceElementContent(contentElement, wrapperElement, { escape: false });
        host.flushDOMUpdates();
        return containerElement;
    };

    const manager = ensureDashboardHardwareWidgetsManager(widgets, ensureContainer());

    if (!widgets.hardwareWidgetsInitialized) {
        if (!widgets.hardwareWidgetsInitializePromise) {
            widgets.hardwareWidgetsInitializePromise = manager.initialize(snapshotCandidate);
        }
        await widgets.hardwareWidgetsInitializePromise;
        if (isDestroyed()) {
            return;
        }
        widgets.hardwareWidgetsInitializePromise = null;
        widgets.hardwareWidgetsInitialized = true;
        const pending = widgets.hardwareWidgetsPendingSnapshot;
        widgets.hardwareWidgetsPendingSnapshot = null;
        if (pending !== null) {
            await manager.handleSnapshotUpdate(pending);
        }
        return;
    }

    await manager.handleSnapshotUpdate(snapshotCandidate);
};

export { destroyHardwareWidgetsManager, renderHardwareWidgetsSection };
