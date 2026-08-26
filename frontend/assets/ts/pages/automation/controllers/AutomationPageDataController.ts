/* SoAI - Automation page data controller [frontend/assets/ts/pages/automation/controllers/AutomationPageDataController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveBufferedAutomationWindow } from '@pages/automation/controllers/automationWindow.ts';
import type { AutomationDataService, AutomationZone } from '@features/automation/public.ts';
import type { AutomationPageState } from '@pages/automation/types.ts';

const loadBufferedWindowZones = async (dataService: AutomationDataService, fromUtcMs: number, toUtcMs: number): Promise<readonly AutomationZone[]> => {
    const pageZones: AutomationZone[] = [];
    let offset = 0;
    while (true) {
        const page = await dataService.getZonesWindow(fromUtcMs, toUtcMs, offset);
        if (page.offset !== offset) {
            throw new Error('Automation occurrences page returned an invalid offset');
        }
        if (page.occurrences.length > page.limit) {
            throw new Error('Automation occurrences page returned more items than its limit');
        }
        pageZones.push(...page.occurrences);
        if (!page.hasMore) {
            break;
        }
        if (page.nextOffset === null || page.nextOffset <= offset) {
            throw new Error('Automation occurrences page returned an invalid nextOffset');
        }
        offset = page.nextOffset;
    }
    return pageZones;
};

class AutomationPageDataController {
    readonly #dataService: AutomationDataService;
    readonly #getState: () => AutomationPageState;
    readonly #setState: (next: AutomationPageState) => void;
    readonly #queueRender: () => void;
    readonly #isDestroyed: () => boolean;
    #loadSeq = 0;
    #windowSignature = '';

    constructor(dependencies: { dataService: AutomationDataService; getState: () => AutomationPageState; setState: (next: AutomationPageState) => void; queueRender: () => void; isDestroyed: () => boolean }) {
        this.#dataService = dependencies.dataService;
        this.#getState = dependencies.getState;
        this.#setState = dependencies.setState;
        this.#queueRender = dependencies.queueRender;
        this.#isDestroyed = dependencies.isDestroyed;
    }

    getWindowSignature(): string {
        return this.#windowSignature;
    }

    async refresh(): Promise<void> {
        const seq = (this.#loadSeq += 1);
        const requestedState = this.#getState();
        const bufferedWindow = resolveBufferedAutomationWindow(requestedState);
        const requestedSignature = bufferedWindow.signature;
        const [automationPage, zones] = await Promise.all([this.#dataService.listAutomations(requestedState.automationRegistryLimit, requestedState.automationRegistryOffset), loadBufferedWindowZones(this.#dataService, bufferedWindow.fromUtcMs, bufferedWindow.toUtcMs)]);

        if (this.#isDestroyed() || seq !== this.#loadSeq) {
            return;
        }

        const currentSignature = resolveBufferedAutomationWindow(this.#getState()).signature;
        if (currentSignature !== requestedSignature) {
            return;
        }

        this.#windowSignature = requestedSignature;
        const currentState = this.#getState();
        this.#setState({
            ...currentState,
            automations: automationPage.automations,
            automationRegistryLimit: automationPage.limit,
            automationRegistryOffset: automationPage.offset,
            automationRegistryHasMore: automationPage.hasMore,
            zones: zones.slice().sort((left, right) => left.scheduledAtMs - right.scheduledAtMs)
        });
        this.#queueRender();
    }
}

export { AutomationPageDataController };
