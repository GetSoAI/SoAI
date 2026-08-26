/* SoAI - Automation feature MCP DOM [frontend/assets/ts/features/automation/modals/mcpDom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolve, resolveAll } from '@core/dom/dom.ts';

const ensureCheckbox = (element: Element, label: string): HTMLInputElement => {
    if (element instanceof HTMLInputElement && element.type === 'checkbox') {
        return element;
    }
    throw new TypeError(`Automation MCP ${label} must be a checkbox input`);
};

const queryCheckboxes = (root: Element, selector: string, label: string): HTMLInputElement[] => {
    const elements = resolveAll(selector, root);
    const inputs: HTMLInputElement[] = [];
    for (const element of elements) {
        inputs.push(ensureCheckbox(element, label));
    }
    return inputs;
};

const queryDisableableControls = (root: Element, selector: string, label: string): Array<HTMLInputElement | HTMLButtonElement> => {
    const elements = resolveAll(selector, root);
    const controls: Array<HTMLInputElement | HTMLButtonElement> = [];
    for (const element of elements) {
        if (element instanceof HTMLInputElement || element instanceof HTMLButtonElement) {
            controls.push(element);
            continue;
        }
        throw new TypeError(`Automation MCP ${label} must contain inputs or buttons`);
    }
    return controls;
};

const requireAutomationMcpToolsList = (modalRoot: Element): HTMLElement => {
    const element = resolve('.mcp-tools-list', modalRoot);
    if (element instanceof HTMLElement) {
        return element;
    }
    throw new Error('Automation MCP tools list is missing');
};

const requireAutomationMcpToolsEmpty = (modalRoot: Element): HTMLElement => {
    const element = resolve('.mcp-tools-empty', modalRoot);
    if (element instanceof HTMLElement) {
        return element;
    }
    throw new Error('Automation MCP tools empty state is missing');
};

const queryAutomationMcpServerToggleInputs = (modalRoot: Element): HTMLInputElement[] => queryCheckboxes(modalRoot, '.mcp-server-toggle', 'server toggles');

const queryAutomationMcpToolToggleInputs = (modalRoot: Element): HTMLInputElement[] => queryCheckboxes(modalRoot, '.mcp-tool-toggle', 'tool toggles');

const queryAutomationMcpModalDisableableControls = (modalRoot: Element): Array<HTMLInputElement | HTMLButtonElement> => queryDisableableControls(modalRoot, '.mcp-input', 'modal controls');

export { queryAutomationMcpModalDisableableControls, queryAutomationMcpServerToggleInputs, queryAutomationMcpToolToggleInputs, requireAutomationMcpToolsEmpty, requireAutomationMcpToolsList };
