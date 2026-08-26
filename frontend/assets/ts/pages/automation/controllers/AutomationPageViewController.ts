/* SoAI - Automation page view controller [frontend/assets/ts/pages/automation/controllers/AutomationPageViewController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { resolveAutomationZoneByKey } from '@pages/automation/contracts/zoneKey.ts';
import type { AutomationCalendarRenderCache } from '@pages/automation/controllers/automationCalendarPresentation.ts';
import { AutomationCheckerboardController } from '@pages/automation/controllers/AutomationCheckerboardController.ts';
import { renderAutomationPage } from '@pages/automation/controllers/AutomationPageRenderer.ts';
import type { AutomationPageUiConnectionsController } from '@pages/automation/controllers/AutomationPageUiConnectionsController.ts';
import type { AutomationWindowRunsPaneController } from '@pages/automation/controllers/windowrunstoolbar/paneController.ts';
import type { AutomationDefinition, AutomationZone } from '@features/automation/public.ts';
import type { AutomationPageState, AutomationUiRefs } from '@pages/automation/types.ts';

type AutomationPageViewControllerDependencies = {
    ui: AutomationUiRefs;
    replaceElementContent: (element: Element, content: string | TrustedHtml, options?: { escape?: boolean }) => void;
    flushDOMUpdates: () => void;
    getIconSync: (icon: IconName, options?: IconOptions) => TrustedHtml;
    getHourHeightPx: () => number;
    getMonthMaxChipsPerDay: () => number;
    getRunningAutomationIds: () => ReadonlySet<string>;
    isPreferencesCorrupt: () => boolean;
    queueRender: () => void;
    windowRunsPane: AutomationWindowRunsPaneController;
    getConnections: () => AutomationPageUiConnectionsController | null;
};

interface AutomationPageDerivedRenderState {
    registryAutomations: readonly AutomationDefinition[];
    selectedAutomationId: string | null;
    mergedRunningAutomationIds: ReadonlySet<string>;
}

class AutomationPageViewController {
    readonly #dependencies: AutomationPageViewControllerDependencies;
    readonly #checkerboard: AutomationCheckerboardController;
    readonly #calendarCache: AutomationCalendarRenderCache = { presentationSignature: '' };
    #derivedCache: {
        automationsRef: readonly AutomationDefinition[];
        zonesRef: readonly AutomationZone[];
        selectedZoneKey: string | null;
        runningAutomationIdsRef: ReadonlySet<string>;
        registryAutomations: readonly AutomationDefinition[];
        selectedAutomationId: string | null;
        mergedRunningAutomationIds: ReadonlySet<string>;
    } | null = null;

    constructor(dependencies: AutomationPageViewControllerDependencies) {
        this.#dependencies = dependencies;
        this.#checkerboard = new AutomationCheckerboardController(dependencies.ui.root);
    }

    #getDerived(state: AutomationPageState): AutomationPageDerivedRenderState {
        const cached = this.#derivedCache;
        const runningAutomationIdsRef = this.#dependencies.getRunningAutomationIds();
        if (cached && cached.automationsRef === state.automations && cached.zonesRef === state.zones && cached.selectedZoneKey === state.selectedZoneKey && cached.runningAutomationIdsRef === runningAutomationIdsRef) {
            return {
                registryAutomations: cached.registryAutomations,
                selectedAutomationId: cached.selectedAutomationId,
                mergedRunningAutomationIds: cached.mergedRunningAutomationIds
            };
        }

        const terminalStatuses: ReadonlySet<AutomationZone['status']> = new Set(['completed', 'error', 'cancelled', 'abandoned']);
        const completedOneShotIds = new Set<string>();
        for (const zone of state.zones) {
            if (!terminalStatuses.has(zone.status)) {
                continue;
            }
            if (zone.finishedAtMs === null) {
                continue;
            }
            completedOneShotIds.add(zone.automationId);
        }
        const registryAutomations = state.automations.filter((automation) => !(automation.recurrence === 'none' && completedOneShotIds.has(automation.id)));

        const selectedZone = state.selectedZoneKey ? resolveAutomationZoneByKey(state.zones, state.selectedZoneKey) : null;
        const selectedAutomationId = selectedZone?.automationId ?? null;

        const mergedRunningAutomationIds = (() => {
            const merged = new Set<string>();
            for (const zone of state.zones) {
                if (zone.status === 'running') {
                    merged.add(zone.automationId);
                }
            }
            for (const automationId of runningAutomationIdsRef) {
                merged.add(automationId);
            }
            return merged;
        })();

        this.#derivedCache = {
            automationsRef: state.automations,
            zonesRef: state.zones,
            selectedZoneKey: state.selectedZoneKey,
            runningAutomationIdsRef,
            registryAutomations,
            selectedAutomationId,
            mergedRunningAutomationIds
        };
        return { registryAutomations, selectedAutomationId, mergedRunningAutomationIds };
    }

    render(state: AutomationPageState): string {
        const derived = this.#getDerived(state);
        const connections = this.#dependencies.getConnections();
        const renderedWindowSignature = this.#renderSettledCalendar(state, derived, connections);
        if (!this.#dependencies.isPreferencesCorrupt()) {
            this.#dependencies.windowRunsPane.bindUi(this.#dependencies.ui.windowRunsRoot, state.zones.length);
            this.#checkerboard.sync();
        }
        connections?.afterRender();
        return renderedWindowSignature;
    }

    #renderSettledCalendar(state: AutomationPageState, derived: AutomationPageDerivedRenderState, connections: AutomationPageUiConnectionsController | null): string {
        const firstPassSignature = this.#renderOnce(state, derived);
        if (!connections || !connections.measureMonthLayout()) {
            return firstPassSignature;
        }
        const settledSignature = this.#renderOnce(state, derived);
        if (connections.measureMonthLayout()) {
            this.#dependencies.queueRender();
        }
        return settledSignature;
    }

    #renderOnce(state: AutomationPageState, derived: AutomationPageDerivedRenderState): string {
        return renderAutomationPage(
            state,
            {
                ui: this.#dependencies.ui,
                replaceElementContent: this.#dependencies.replaceElementContent,
                flushDOMUpdates: this.#dependencies.flushDOMUpdates,
                hourHeightPx: this.#dependencies.getHourHeightPx(),
                getIconSync: this.#dependencies.getIconSync
            },
            {
                monthMaxChipsPerDay: this.#dependencies.getMonthMaxChipsPerDay(),
                calendarCache: this.#calendarCache,
                registryAutomations: derived.registryAutomations,
                selectedAutomationId: derived.selectedAutomationId,
                runningAutomationIds: derived.mergedRunningAutomationIds,
                registryLimit: state.automationRegistryLimit,
                registryOffset: state.automationRegistryOffset,
                registryHasMore: state.automationRegistryHasMore,
                visibleWindowRuns: state.zones,
                preferencesCorrupt: this.#dependencies.isPreferencesCorrupt(),
                totalWindowRunsCount: state.zones.length,
                windowRunsSelectionActive: this.#dependencies.windowRunsPane.isSelectionActive(),
                windowRunsSelectedKeys: this.#dependencies.windowRunsPane.selectedKeys()
            }
        );
    }

    destroy(): void {
        this.#checkerboard.destroy();
    }
}

export { AutomationPageViewController };
