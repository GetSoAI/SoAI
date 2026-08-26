/* SoAI - Automation page checkerboard controller [frontend/assets/ts/pages/automation/controllers/AutomationCheckerboardController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { checkerboardService, resolveAll } from '@core/dom/dom.ts';

interface CheckerboardTarget {
    container: Element;
    itemSelector: string;
}

const appendCheckerboardTargets = (targets: CheckerboardTarget[], containers: readonly Element[], itemSelector: string): void => {
    for (const container of containers) {
        targets.push({ container, itemSelector });
    }
};

const queryElements = (root: HTMLElement, selector: string): Element[] => resolveAll(selector, root);

const resolveAutomationCheckerboardTargets = (root: HTMLElement): CheckerboardTarget[] => {
    const targets: CheckerboardTarget[] = [];
    appendCheckerboardTargets(targets, queryElements(root, '.automation-month-grid'), '.automation-month-day');
    appendCheckerboardTargets(targets, queryElements(root, '.automation-week-header-days'), '.automation-week-header-day');
    appendCheckerboardTargets(targets, queryElements(root, '.automation-week-columns'), '.automation-week-column');
    appendCheckerboardTargets(targets, queryElements(root, '#automation-registry-scroll'), '.automation-automation-row, .automation-window-run-item');
    return targets;
};

class AutomationCheckerboardController {
    readonly #root: HTMLElement;
    #targetIds: string[] = [];

    constructor(root: HTMLElement) {
        this.#root = root;
    }

    sync(): void {
        const targets = resolveAutomationCheckerboardTargets(this.#root);
        const nextTargetIds: string[] = [];
        for (const target of targets) {
            checkerboardService.applyCheckerboard(target.container, target.itemSelector);
            nextTargetIds.push(checkerboardService.getContainerId(target.container));
        }
        for (const targetId of this.#targetIds) {
            if (!nextTargetIds.includes(targetId)) {
                checkerboardService.disconnect(targetId);
            }
        }
        this.#targetIds = nextTargetIds;
    }

    destroy(): void {
        for (const targetId of this.#targetIds) {
            checkerboardService.disconnect(targetId);
        }
        this.#targetIds = [];
    }
}

export { AutomationCheckerboardController };
