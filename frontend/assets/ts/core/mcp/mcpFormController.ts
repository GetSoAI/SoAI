/* SoAI - Canonical MCP execution settings form controller [frontend/assets/ts/core/mcp/mcpFormController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { bindResolvedDataActionListener } from '@core/dom/dataActionBinding.ts';
import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import type { McpConfig, McpFormCatalog, McpFormValues, McpToolMode } from '@core/mcp/configTypes.ts';
import { isMcpToolServerEnabled } from '@core/mcp/serverSettings.ts';
import { applyMcpToolGroupToggle } from '@core/mcp/toolGroupToggle.ts';
import { renderMcpToolModeGroups } from '@core/mcp/toolModeRendering.ts';
import { filterMcpToolGroupTools } from '@core/mcp/toolSearchFilter.ts';
import { toTrustedHtml, type TrustedHtml } from '@core/security/public.ts';
import { createToggleSwitch, updateToggleLabel } from '@core/toggleSwitch.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

interface McpFormActions {
    serverToggle: string;
    toolToggle: string;
    toolModeSelect: string;
    toolGroupToggle: string;
    toolSearch: string;
}

interface McpFormControllerOptions {
    root: HTMLElement;
    toolsList: HTMLElement;
    toolsEmpty: HTMLElement;
    modalId: string;
    actions: McpFormActions;
    toolModes: readonly McpToolMode[];
    initialToolMode: McpToolMode;
    getIconSync: (icon: IconName, options?: IconOptions) => TrustedHtml;
}

const MCP_FORM_EVENT_TYPES: readonly ('change' | 'click' | 'input')[] = ['change', 'click', 'input'];

const createRenderHost = () => ({
    createElement: (tag: string, options?: Record<string, JsonValue>, content?: string | Node): HTMLElement => {
        const element = document.createElement(tag);
        Object.entries(options ?? {}).forEach(([key, value]) => element.setAttribute(key, String(value)));
        if (typeof content === 'string') element.textContent = content;
        else if (content) element.append(content);
        return element;
    },
    appendToElement: (parent: Element, child: Node | Node[]): void => {
        if (Array.isArray(child)) child.forEach((entry) => parent.append(entry));
        else parent.append(child);
    },
    updateHTML: (element: Element, html: string): void => dom.setHTML(element, toTrustedHtml(html), { escape: false }),
    updateText: (element: Element, value: string): void => {
        element.textContent = value;
    },
    toggleClassName: (element: Element, className: string, add: boolean): void => {
        element.classList.toggle(className, add);
    },
    dom: { getDocument: (): Document => document }
});

const cloneMcpFormValues = (config: McpFormValues): McpFormValues => ({
    defaultTools: [...config.defaultTools],
    planTools: [...config.planTools],
    executeTools: [...config.executeTools],
    serverConfigs: { ...config.serverConfigs },
    toolsEnabled: config.toolsEnabled,
    toolApprovalRequired: config.toolApprovalRequired
});

const readMcpFormValues = (root: Element, baseline: Pick<McpFormValues, 'toolsEnabled' | 'toolApprovalRequired'>): McpFormValues => {
    const serverConfigs: Record<string, boolean> = {};
    dom.resolveAll('.mcp-server-toggle', root).forEach((element) => {
        if (!(element instanceof HTMLInputElement)) throw new Error('MCP server toggle must be an input');
        const serverId = requireTrimmedDataAttribute(element, 'serverId', 'MCP server toggle');
        if (!element.checked) serverConfigs[serverId] = false;
    });
    const selections: Record<McpToolMode, string[]> = { default: [], plan: [], execute: [] };
    dom.resolveAll('.mcp-tool-toggle', root).forEach((element) => {
        if (!(element instanceof HTMLInputElement)) throw new Error('MCP tool toggle must be an input');
        const serverId = requireTrimmedDataAttribute(element, 'serverId', 'MCP tool toggle');
        const mode = requireTrimmedDataAttribute(element, 'toolMode', 'MCP tool toggle');
        if (mode !== 'default' && mode !== 'plan' && mode !== 'execute') throw new Error('MCP tool toggle has an invalid mode');
        const name = requireTrimmedDataAttribute(element, 'toolName', 'MCP tool toggle');
        if (element.checked && isMcpToolServerEnabled(serverId, serverConfigs)) selections[mode].push(name);
    });
    const toolsEnabled = dom.resolve('.mcp-tools-enabled-toggle', root);
    const approvalRequired = dom.resolve('.mcp-tool-approval-required-toggle', root);
    return {
        defaultTools: selections.default,
        planTools: selections.plan,
        executeTools: selections.execute,
        serverConfigs,
        toolsEnabled: toolsEnabled instanceof HTMLInputElement ? toolsEnabled.checked : baseline.toolsEnabled,
        toolApprovalRequired: approvalRequired instanceof HTMLInputElement ? approvalRequired.checked : baseline.toolApprovalRequired
    };
};

const applyMcpServerAvailability = (root: Element, serverConfigs: Record<string, boolean>, readOnly: boolean): void => {
    dom.resolveAll('.mcp-input, .mcp-tool-mode-tabs button', root).forEach((element) => {
        if (!(element instanceof HTMLInputElement || element instanceof HTMLButtonElement)) throw new Error('MCP control must be an input or button');
        element.disabled = readOnly;
    });
    dom.resolveAll('.mcp-tool-toggle', root).forEach((element) => {
        if (!(element instanceof HTMLInputElement)) throw new Error('MCP tool toggle must be an input');
        const enabled = isMcpToolServerEnabled(requireTrimmedDataAttribute(element, 'serverId', 'MCP tool toggle'), serverConfigs);
        element.disabled = readOnly || !enabled;
        if (!enabled) element.checked = false;
        updateToggleLabel(element, { checked: element.checked });
    });
};

class McpFormController {
    readonly #options: McpFormControllerOptions;
    readonly #abort = new AbortController();
    readonly #expandedToolGroupIds = new Set<string>();
    readonly #host = createRenderHost();
    #catalog: McpFormCatalog | null = null;
    #config: McpFormValues;
    #activeToolMode: McpToolMode;
    #readOnly = false;

    constructor(options: McpFormControllerOptions) {
        this.#options = options;
        this.#activeToolMode = options.initialToolMode;
        this.#config = { defaultTools: [], planTools: [], executeTools: [], serverConfigs: {}, toolsEnabled: true, toolApprovalRequired: true };
        for (const eventType of MCP_FORM_EVENT_TYPES) {
            bindResolvedDataActionListener({
                root: options.root,
                eventType,
                signal: this.#abort.signal,
                preventDefault: 'never',
                ignoreDisabled: true,
                onAction: ({ actionElement }): void => this.#handleAction(eventType, actionElement)
            });
        }
    }

    setCatalog(catalog: McpFormCatalog): void {
        const tools = catalog.tools.filter((tool) => tool.allowed);
        const names = new Set(tools.map((tool) => tool.name));
        this.#catalog = {
            tools,
            defaultTools: catalog.defaultTools.filter((name) => names.has(name)),
            planTools: catalog.planTools.filter((name) => names.has(name)),
            executeTools: catalog.executeTools.filter((name) => names.has(name))
        };
        if (this.#config.defaultTools.length + this.#config.planTools.length + this.#config.executeTools.length === 0) {
            this.#config.defaultTools = [...this.#catalog.defaultTools];
            this.#config.planTools = [...this.#catalog.planTools];
            this.#config.executeTools = [...this.#catalog.executeTools];
        }
        this.#render();
    }

    setValues(config: McpFormValues): void {
        this.#config = cloneMcpFormValues(config);
        this.#render();
    }

    setReadOnly(readOnly: boolean): void {
        this.#readOnly = readOnly;
        this.#applyAvailability(this.readConfig().serverConfigs);
    }

    readConfig(): McpFormValues {
        return readMcpFormValues(this.#options.root, this.#config);
    }

    destroy(): void {
        this.#abort.abort();
    }

    #handleAction(eventType: 'change' | 'click' | 'input', element: HTMLElement): void {
        const action = requireTrimmedDataAttribute(element, 'action', 'MCP form action');
        const actions = this.#options.actions;
        if (eventType === 'change' && element instanceof HTMLInputElement) {
            updateToggleLabel(element, { checked: element.checked });
            if (action === actions.serverToggle) this.#applyAvailability(this.readConfig().serverConfigs);
            return;
        }
        if (eventType === 'click' && action === actions.toolModeSelect) {
            const mode = requireTrimmedDataAttribute(element, 'toolMode', 'MCP tool mode');
            if (mode !== 'default' && mode !== 'plan' && mode !== 'execute') throw new Error('MCP tool mode is invalid');
            this.#config = this.readConfig();
            this.#activeToolMode = mode;
            this.#render();
            return;
        }
        if (eventType === 'click' && action === actions.toolGroupToggle) {
            const result = applyMcpToolGroupToggle(element);
            if (result.expanded) this.#expandedToolGroupIds.add(result.serverId);
            else this.#expandedToolGroupIds.delete(result.serverId);
            return;
        }
        if (eventType === 'input' && action === actions.toolSearch) filterMcpToolGroupTools(element);
    }

    #buildToggle = (options: { id: string; checked: boolean; disabled?: boolean; className: string; data?: Record<string, string> }): HTMLElement => {
        const action = options.className.includes('mcp-server-toggle') ? this.#options.actions.serverToggle : this.#options.actions.toolToggle;
        return createToggleSwitch({ id: options.id, checked: options.checked, labels: { trueLabel: i18n.t('common.enabled'), falseLabel: i18n.t('common.disabled') }, inline: true, disabled: options.disabled, inputClassName: options.className, inputDataset: { ...(options.data ?? {}), action }, wrapperTag: 'div' });
    };

    #applyAvailability(serverConfigs: Record<string, boolean>): void {
        applyMcpServerAvailability(this.#options.root, serverConfigs, this.#readOnly);
    }

    #syncTopLevelToggles(): void {
        const toolsEnabled = dom.resolve('.mcp-tools-enabled-toggle', this.#options.root);
        const approvalRequired = dom.resolve('.mcp-tool-approval-required-toggle', this.#options.root);
        if (toolsEnabled instanceof HTMLInputElement) {
            toolsEnabled.checked = this.#config.toolsEnabled;
            updateToggleLabel(toolsEnabled, { checked: toolsEnabled.checked });
        }
        if (approvalRequired instanceof HTMLInputElement) {
            approvalRequired.checked = this.#config.toolApprovalRequired;
            updateToggleLabel(approvalRequired, { checked: approvalRequired.checked });
        }
    }

    #render(): void {
        if (!this.#catalog) return;
        this.#syncTopLevelToggles();
        const config: McpConfig<null> = { ...cloneMcpFormValues(this.#config), knowledgeState: null };
        renderMcpToolModeGroups({ host: this.#host, container: this.#options.toolsList, emptyState: this.#options.toolsEmpty, config, tools: this.#catalog.tools, activeToolTab: this.#activeToolMode, toolModes: this.#options.toolModes, toolModeAction: this.#options.actions.toolModeSelect, buildToggleSwitch: this.#buildToggle, toggleIdPrefix: `${this.#options.modalId}-mcp-tool-toggle`, applyServerToolAvailability: (serverConfigs) => this.#applyAvailability(serverConfigs), collapsedToolGroups: true, toolGroupToggleAction: this.#options.actions.toolGroupToggle, toolGroupToggleIcon: this.#options.getIconSync('chevron-left', { size: 14, strokeWidth: 2 }), expandedToolGroupIds: this.#expandedToolGroupIds, showServerToggles: true, toolSearchAction: this.#options.actions.toolSearch });
        this.#applyAvailability(config.serverConfigs);
    }
}

export { McpFormController, applyMcpServerAvailability, readMcpFormValues };
export type { McpFormActions, McpFormControllerOptions };
