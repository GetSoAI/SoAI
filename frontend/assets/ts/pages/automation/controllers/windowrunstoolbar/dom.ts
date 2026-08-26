/* SoAI - Automation page window runs toolbar DOM contracts [frontend/assets/ts/pages/automation/controllers/windowrunstoolbar/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolve, resolveAll } from '@core/dom/dom.ts';
import { narrowButton, narrowHTMLElement } from '@core/dom/narrowElement.ts';
import type { AutomationWindowRunsToolbarUiRefs } from '@pages/automation/controllers/windowrunstoolbar/types.ts';

const requireElement = (root: Element, selector: string, label: string): HTMLElement => {
    const element = resolve(selector, root);
    if (!element) {
        throw new Error(`Automation window runs ${label} is missing`);
    }
    return narrowHTMLElement(element, `Automation window runs ${label}`);
};

const requireButton = (root: Element, selector: string, label: string): HTMLButtonElement => {
    return narrowButton(requireElement(root, selector, label), `Automation window runs ${label}`);
};

const resolveAutomationWindowRunsToolbarUi = (windowRunsRoot: HTMLElement): AutomationWindowRunsToolbarUiRefs => {
    return {
        toolbarContainer: requireElement(windowRunsRoot, '#automation-window-runs-toolbar-container', 'toolbar container'),
        runsList: requireElement(windowRunsRoot, '#automation-window-runs-list', 'runs list'),
        totalRunsIcon: requireElement(windowRunsRoot, '.automation-window-runs-total-icon', 'total icon'),
        totalRunsLabel: requireElement(windowRunsRoot, '.automation-window-runs-total', 'total label'),
        selectedCountIcon: requireElement(windowRunsRoot, '.automation-window-runs-selected-icon', 'selected icon'),
        selectedCountLabel: requireElement(windowRunsRoot, '.automation-window-runs-selected', 'selected label'),
        selectButton: requireElement(windowRunsRoot, '.automation-window-runs-select-btn', 'select button'),
        batchActionsContainer: requireElement(windowRunsRoot, '.automation-window-runs-toolbar-batch-actions', 'batch actions container'),
        batchDeleteButton: requireButton(windowRunsRoot, '.automation-window-runs-batch-delete-btn', 'batch delete button'),
        exitSelectButton: requireElement(windowRunsRoot, '.automation-window-runs-exit-select-btn', 'exit select button')
    };
};

const queryAutomationWindowRunItems = (runsList: HTMLElement): HTMLElement[] => {
    const candidates = resolveAll('.automation-window-run-item', runsList);
    const items: HTMLElement[] = [];
    for (const candidate of candidates) {
        if (candidate instanceof HTMLElement) {
            items.push(candidate);
        }
    }
    return items;
};

export { queryAutomationWindowRunItems, resolveAutomationWindowRunsToolbarUi };
