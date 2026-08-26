/* SoAI - Settings feature MCP interactions [frontend/assets/ts/features/settings/mcp/mcpInteractions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireClosestElement } from '@core/dom/attributes.ts';
import { dom } from '@core/dom/dom.ts';
import { readTrimmedInputValue } from '@core/dom/formValues.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import type { McpInteractionAction, McpInteractionConfig, McpInteractionEntry, McpInteractionMode } from '@core/mcp/contracts.ts';
import { formatPositiveEpochMsWithFallback } from '@core/primitives/dateTime.ts';
import { renderLabelAttributes } from '@core/security/public.ts';
import { parseRequiredJsonObjectText } from '@core/serialization/json.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { renderSettingsRecordList } from '@core/settings/settingsMarkup.ts';
import { renderControlDisabledAttributes, setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { renderStandardDropdownSelectControl } from '@core/ui/dropdown/selectControl.ts';
import { renderEmptyState } from '@core/ui/emptyState.ts';
import { UI_IDS } from '@features/settings/contracts/SettingsPageSupport.ts';
import type { PageSanitizer } from '@features/settings/contracts/contracts.ts';
import { MCP_ACTION_INTERACTION_ACTION_CHANGE, MCP_ACTION_INTERACTION_RESOLVE } from '@features/settings/mcp/actions.ts';
import type { McpManagerHost } from '@features/settings/mcp/mcpManagerTypes.ts';
import type { McpSectionExpansionResolver } from '@features/settings/mcp/mcpSectionExpansionState.ts';
import { renderMcpCollapsibleSection } from '@features/settings/mcp/renderCollapsibleSection.ts';

type McpInteractionsHost = Pick<McpManagerHost, 'services' | 'view' | 'execution' | 'data'>;

interface McpInteractionsDependencies {
    host: McpInteractionsHost;
    reload: () => Promise<boolean>;
}

class McpInteractionsManager {
    readonly #host: McpInteractionsHost;
    readonly #reload: () => Promise<boolean>;

    constructor({ host, reload }: McpInteractionsDependencies) {
        this.#host = host;
        this.#reload = reload;
    }

    renderSubgroup(resolveExpanded: McpSectionExpansionResolver): string {
        const mcpData = this.#host.data.getMcpData();
        return renderMcpCollapsibleSection({
            id: 'interactions',
            title: i18n.t('settings.mcp.interactions.title'),
            description: i18n.t('settings.mcp.interactions.description'),
            className: 'settings-section--mcp settings-section--mcp-interactions',
            content: renderSettingsRecordList({
                id: UI_IDS.MCP_INTERACTIONS_LIST,
                items: mcpData.interactions.map((interaction) => this.#renderInteractionItem(interaction)),
                empty: renderEmptyState({ title: i18n.t('settings.mcp.interactions.empty'), className: 'ui-empty-state--simple' }).html
            }),
            expanded: mcpData.interactions.length > 0,
            resolveExpanded
        });
    }

    updateInteractionButton(select: HTMLSelectElement): void {
        const container = requireClosestElement(select, '.settings-record-item', 'MCP interaction select');

        const buttonElement = dom.resolve('.mcp-interaction-resolve-btn', container);
        if (!(buttonElement instanceof HTMLButtonElement)) {
            throw new Error('MCP interaction resolve button missing or invalid');
        }

        const taskId = this.#host.services.dom.getData(container, 'task_id');
        if (!taskId) {
            throw new Error('MCP interaction item missing data-task-id');
        }
        const entry = this.#requireInteractionEntry(taskId);
        const config = this.#resolveInteractionConfig(entry);
        const action = this.#requireActionValue(select.value, config);
        buttonElement.textContent = resolveInteractionActionLabel(action);

        const contentElement = dom.resolve('.mcp-interaction-content', container);
        if (!(contentElement instanceof HTMLTextAreaElement)) {
            throw new Error('MCP interaction content textarea missing or invalid');
        }
        const rule = this.#resolveInteractionContentRule(config.mode, action);
        setControlDisabledState(contentElement, config.mode === 'unknown' || rule !== 'required');
    }

    async resolveInteraction(button: Element, taskId: string): Promise<void> {
        const container = requireClosestElement(button, '.settings-record-item', 'MCP interaction resolve button');

        const selectElement = dom.resolve('.mcp-interaction-action', container);
        if (!(selectElement instanceof HTMLSelectElement)) {
            throw new Error('MCP interaction action select missing or invalid');
        }
        const contentElement = dom.resolve('.mcp-interaction-content', container);
        if (!(contentElement instanceof HTMLTextAreaElement)) {
            throw new Error('MCP interaction content textarea missing or invalid');
        }

        const entry = this.#requireInteractionEntry(taskId);
        const config = this.#resolveInteractionConfig(entry);
        if (config.mode === 'unknown') {
            this.#host.execution.feedback.show(i18n.t('settings.mcp.notifications.interactionUnsupported'), 'error');
            return;
        }

        const action = this.#requireActionValue(selectElement.value, config);
        const rule = this.#resolveInteractionContentRule(config.mode, action);
        let content: JsonObject | null = null;
        if (rule === 'required') {
            const contentText = readTrimmedInputValue(contentElement);
            if (!contentText) {
                return this.#host.view.warnAndFocus(contentElement, i18n.t('settings.mcp.notifications.interactionContentRequired'));
            }
            try {
                content = parseRequiredJsonObjectText(contentText, i18n.t('settings.mcp.notifications.jsonInvalid'));
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.debug('SettingsPage', 'MCP interaction JSON validation failed', runtimeError);
                return this.#host.view.warnAndFocus(contentElement, i18n.t('settings.mcp.notifications.jsonInvalid'));
            }
        }

        await this.#host.execution.runWithBoundary('settings:resolveMcpInteraction', async () => {
            await this.#host.execution.withButtonDisabled(button, async () => {
                await this.#host.services.api.mcp.interactions.resolve(taskId, { action, ...(content ? { content } : {}) });
                this.#host.execution.feedback.show(i18n.t('settings.mcp.notifications.interactionResolved'), 'success');
            });
            await this.#reload();
        });
    }

    #renderInteractionItem(interaction: McpInteractionEntry): string {
        const sanitizer = this.#host.services.pageContext.sanitizer;
        const config = this.#resolveInteractionConfig(interaction);
        const info = this.#buildInteractionInfo(interaction, sanitizer);
        const actions = this.#buildInteractionActions(interaction, sanitizer, config);
        return `<div class="settings-record-item" data-task-id="${sanitizer.attribute(interaction.taskId)}">${info}${actions}</div>`;
    }

    #buildInteractionInfo(interaction: McpInteractionEntry, sanitizer: PageSanitizer): string {
        const statusClass = interaction.status === 'pending' ? 'settings-record-badge--info' : 'settings-record-badge--neutral';
        const placeholderUnknown = i18n.t('settings.mcp.interactions.placeholderUnknown');
        const placeholderDash = i18n.t('settings.mcp.interactions.placeholderDash');
        const createdDate = formatPositiveEpochMsWithFallback(interaction.createdAtMs, placeholderDash);
        const methodLabel = sanitizer.html(interaction.method ? interaction.method : placeholderUnknown);
        const statusLabel = sanitizer.html(interaction.status ? interaction.status : placeholderUnknown);
        const clientId = sanitizer.html(interaction.clientId ? interaction.clientId : placeholderDash);
        const createdAt = sanitizer.html(createdDate);

        const clientMeta = i18n.t('settings.mcp.interactions.meta.client', { id: clientId });
        const createdMeta = i18n.t('settings.mcp.interactions.meta.created_at', { time: createdAt });
        return `<div class="settings-record-info mcp-interaction-info"><div class="settings-record-header mcp-interaction-header"><span class="settings-record-label mcp-interaction-method">${methodLabel}</span><span class="settings-record-badge ${statusClass}">${statusLabel}</span></div><div class="settings-record-meta mcp-interaction-meta"><span>${clientMeta}</span><span>${createdMeta}</span></div></div>`;
    }

    #buildInteractionActions(interaction: McpInteractionEntry, sanitizer: PageSanitizer, config: McpInteractionConfig): string {
        const taskId = sanitizer.attribute(interaction.taskId);
        const firstAction = config.actions[0];
        const defaultAction: McpInteractionAction = firstAction ? firstAction : 'cancel';

        const options = config.actions
            .map((action) => {
                const selected = action === defaultAction ? ' selected' : '';
                return `<option value="${action}"${selected}>${resolveInteractionActionLabel(action)}</option>`;
            })
            .join('');

        const defaultRule = this.#resolveInteractionContentRule(config.mode, defaultAction);
        const contentDisabled = config.mode === 'unknown' || defaultRule !== 'required';
        const select = renderStandardDropdownSelectControl(`<select data-action="${MCP_ACTION_INTERACTION_ACTION_CHANGE}" class="setting-input mcp-interaction-action">${options}</select>`);
        const placeholder = sanitizer.attribute(i18n.t('settings.mcp.interactions.contentPlaceholder'));
        const contentInput = `<textarea class="setting-textarea mcp-interaction-content" rows="4" placeholder="${placeholder}"${renderControlDisabledAttributes(contentDisabled)}></textarea>`;
        const buttonText = resolveInteractionActionLabel(defaultAction);
        const button = `<button type="button" data-action="${MCP_ACTION_INTERACTION_RESOLVE}" class="ui-button ui-button--sm ui-variant-primary mcp-interaction-resolve-btn" data-task-id="${taskId}" ${renderLabelAttributes(buttonText)}>${buttonText}</button>`;
        return `<div class="mcp-interaction-actions">${select}${contentInput}${button}</div>`;
    }

    #requireInteractionEntry(taskId: string): McpInteractionEntry {
        const mcpData = this.#host.data.getMcpData();
        const entry = mcpData.interactions.find((item) => item.taskId === taskId) ?? null;
        if (!entry) {
            throw new Error('MCP interaction entry missing from state');
        }
        return entry;
    }

    #requireActionValue(raw: string, config: McpInteractionConfig): McpInteractionAction {
        const candidate = raw.trim();
        const value = config.actions.find((action) => action === candidate) ?? null;
        if (!value) {
            throw new Error('MCP interaction action value is invalid for mode');
        }
        return value;
    }

    #resolveInteractionConfig(entry: McpInteractionEntry): McpInteractionConfig {
        const method = entry.method ?? '';
        if (method === 'elicitation/create') {
            const parameters = entry.parameters;
            const rawMode = parameters ? parameters['mode'] : null;
            const resolvedModeValue = typeof rawMode === 'string' ? rawMode.trim().toLowerCase() : '';
            const mode: McpInteractionMode = resolvedModeValue === 'url' ? 'elicitation-url' : 'elicitation-form';
            return { actions: ['accept', 'decline', 'cancel'], mode };
        }
        if (method === 'sampling/createMessage') {
            return { actions: ['approve', 'decline', 'cancel'], mode: 'sampling' };
        }
        return { actions: ['cancel'], mode: 'unknown' };
    }

    #resolveInteractionContentRule(mode: McpInteractionMode, action: McpInteractionAction): 'required' | 'forbidden' {
        if (mode === 'elicitation-form' && action === 'accept') {
            return 'required';
        }
        return 'forbidden';
    }
}

export { McpInteractionsManager };

const resolveInteractionActionLabel = (action: McpInteractionAction): string => {
    switch (action) {
        case 'approve':
            return i18n.t('settings.mcp.interactions.actions.approve');
        case 'accept':
            return i18n.t('settings.mcp.interactions.actions.accept');
        case 'decline':
            return i18n.t('settings.mcp.interactions.actions.decline');
        case 'cancel':
            return i18n.t('settings.mcp.interactions.actions.cancel');
        default: {
            const exhaustive: never = action;
            throw new Error(`Unhandled MCP interaction action: ${exhaustive}`);
        }
    }
};
