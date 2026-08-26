/* SoAI - MCP conversation settings DOM contracts [frontend/assets/ts/features/chat/conversationsettings/mcpconversationsettingscontroller/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { createElementResolver } from '@core/dom/elementResolver.ts';
import { requireInputElement, type ElementResolver } from '@core/dom/typedElements.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { createToggleSwitch, updateToggleLabel } from '@core/toggleSwitch.ts';
import { i18n } from '@core/i18n/index.ts';
import { MCP_CONVERSATION_ACTION_DEFAULT_TOOL_TOGGLE, MCP_CONVERSATION_ACTION_SERVER_TOGGLE, MCP_CONVERSATION_ACTION_TOOL_TOGGLE } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/actionIds.ts';
import type { McpToggleSwitchOptions } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/types.ts';
import type { ConversationSettingsHost } from '@features/chat/conversationsettings/conversationSettingsHost.ts';
import { CHAT_MCP_DEFAULT_TOOLS_MODAL_ID } from '@features/chat/modals/constants.ts';

const requireModalRoot = (modalRoot: Element | null): Element => {
    if (!modalRoot) {
        throw new Error('Chat conversation settings require a modal root element');
    }
    return modalRoot;
};

const requireDefaultToolsModalRoot = (defaultToolsModalRoot: Element | null): Element => {
    if (!defaultToolsModalRoot) {
        throw new Error('Chat conversation settings require a default tools modal root element');
    }
    return defaultToolsModalRoot;
};

const createSettingsResolver = (root: Element | null, prefix: string): ElementResolver => createElementResolver(requireModalRoot(root), prefix);
const createDefaultToolsResolver = (root: Element | null, prefix: string): ElementResolver => createElementResolver(requireDefaultToolsModalRoot(root), prefix);

const requireModalElement = (modalRoot: Element | null, selector: string): Element => {
    return createSettingsResolver(modalRoot, 'Chat conversation settings').requireHTMLElement(selector);
};

const requireDefaultToolsModalElement = (defaultToolsModalRoot: Element | null, selector: string): Element => {
    return createDefaultToolsResolver(defaultToolsModalRoot, 'Chat conversation settings default tools').requireHTMLElement(selector);
};

const requireModalInput = (modalRoot: Element | null, selector: string): HTMLInputElement => {
    const resolver = createSettingsResolver(modalRoot, 'Chat conversation settings');
    return requireInputElement(resolver, selector, `Chat conversation settings input ${selector}`);
};

const resolveCheckboxFromElement = (element: Element): HTMLInputElement | null => {
    if (element instanceof HTMLInputElement && element.type === 'checkbox') {
        return element;
    }
    if (element instanceof HTMLLabelElement) {
        const control = element.control;
        if (control instanceof HTMLInputElement && control.type === 'checkbox') {
            return control;
        }
    }
    const nestedCheckbox = dom.resolve('input[type="checkbox"]', element);
    if (nestedCheckbox instanceof HTMLInputElement && nestedCheckbox.type === 'checkbox') {
        return nestedCheckbox;
    }
    const toggleRoot = element.closest('.toggle-switch');
    if (!toggleRoot) {
        return null;
    }
    const toggleCheckbox = dom.resolve('input[type="checkbox"]', toggleRoot);
    if (toggleCheckbox instanceof HTMLInputElement && toggleCheckbox.type === 'checkbox') {
        return toggleCheckbox;
    }
    return null;
};

const requireToggleCheckbox = (element: Element): HTMLInputElement => {
    const input = resolveCheckboxFromElement(element);
    if (!input) {
        throw new TypeError('Chat conversation settings toggle must be a checkbox input');
    }
    return input;
};

const updateToggleState = (element: Element): void => {
    const input = requireToggleCheckbox(element);
    updateToggleLabel(input, { checked: input.checked });
};

const queryModalElements = (modalRoot: Element | null, selector: string): Element[] => Array.from(dom.resolveAll(selector, requireModalRoot(modalRoot)));

const queryDefaultToolsModalElements = (defaultToolsModalRoot: Element | null, selector: string): Element[] => Array.from(dom.resolveAll(selector, requireDefaultToolsModalRoot(defaultToolsModalRoot)));

const readExpandedToolGroupIds = (root: Element | null): Set<string> => {
    const expanded = new Set<string>();
    for (const group of dom.resolveAll('.mcp-tool-group.is-expanded[data-server-id]', requireModalRoot(root))) {
        if (group instanceof HTMLElement && group.dataset['serverId']) {
            expanded.add(group.dataset['serverId']);
        }
    }
    return expanded;
};

const openDefaultToolsModal = (): void => {
    requireModalPresenter().open(CHAT_MCP_DEFAULT_TOOLS_MODAL_ID);
};

const resolveMcpToggleAction = (className: string): string => {
    if (className.includes('mcp-server-toggle')) {
        return MCP_CONVERSATION_ACTION_SERVER_TOGGLE;
    }
    if (className.includes('mcp-default-tool-toggle')) {
        return MCP_CONVERSATION_ACTION_DEFAULT_TOOL_TOGGLE;
    }
    if (className.includes('mcp-tool-toggle')) {
        return MCP_CONVERSATION_ACTION_TOOL_TOGGLE;
    }
    throw new Error('Chat MCP toggle action requires a known toggle class');
};

const buildMcpToggleSwitch = (options: McpToggleSwitchOptions): HTMLElement =>
    createToggleSwitch({
        id: options.id,
        checked: options.checked,
        labels: {
            trueLabel: i18n.t('chat.parameters.enabled'),
            falseLabel: i18n.t('chat.parameters.disabled')
        },
        inline: true,
        disabled: options.disabled,
        inputClassName: options.className,
        inputDataset: { ...(options.data ?? {}), action: resolveMcpToggleAction(options.className) },
        wrapperTag: 'div'
    });

const readData = (host: ConversationSettingsHost, element: Element, key: string): string | null => {
    const value = host.view.dom.getData(element, key);
    return typeof value === 'string' && value.trim() ? value.trim() : null;
};

export { buildMcpToggleSwitch, openDefaultToolsModal, queryDefaultToolsModalElements, queryModalElements, readData, readExpandedToolGroupIds, requireDefaultToolsModalElement, requireModalElement, requireModalInput, requireToggleCheckbox, updateToggleState };
