/* SoAI - Settings feature MCP roots [frontend/assets/ts/features/settings/mcp/mcpRoots.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readOptionalTrimmedInputValue, readTrimmedInputValue } from '@core/dom/formValues.ts';
import { i18n } from '@core/i18n/index.ts';
import type { McpRootEntry } from '@core/mcp/contracts.ts';
import { createSettingsManualFieldKey } from '@core/settings/settingsFieldKeys.ts';
import { renderSettingItem, renderSettingsGroup, renderSettingsRecordList } from '@core/settings/settingsMarkup.ts';
import { renderEmptyState } from '@core/ui/emptyState.ts';
import { UI_IDS } from '@features/settings/contracts/SettingsPageSupport.ts';
import type { PageSanitizer } from '@features/settings/contracts/contracts.ts';
import { MCP_ACTION_ROOT_CANCEL, MCP_ACTION_ROOT_DELETE, MCP_ACTION_ROOT_EDIT } from '@features/settings/mcp/actions.ts';
import type { McpManagerHost } from '@features/settings/mcp/mcpManagerTypes.ts';
import type { McpSectionExpansionResolver } from '@features/settings/mcp/mcpSectionExpansionState.ts';
import { renderMcpCollapsibleSection } from '@features/settings/mcp/renderCollapsibleSection.ts';

type McpRootsHost = Pick<McpManagerHost, 'services' | 'view' | 'execution' | 'data' | 'editing'>;

interface McpRootsDependencies {
    host: McpRootsHost;
    reload: () => Promise<boolean>;
    rerender: () => void;
}

class McpRootsManager {
    readonly #host: McpRootsHost;
    readonly #reload: () => Promise<boolean>;
    readonly #rerender: () => void;

    constructor({ host, reload, rerender }: McpRootsDependencies) {
        this.#host = host;
        this.#reload = reload;
        this.#rerender = rerender;
    }

    hasPendingChanges(): boolean {
        const uriInput = this.#host.view.pageDom.optional('mcp-root-uri-input');
        if (!(uriInput instanceof HTMLInputElement)) {
            return false;
        }
        const nameInput = this.#host.view.pageDom.optional('mcp-root-name-input');
        return uriInput.value !== uriInput.defaultValue || (nameInput instanceof HTMLInputElement && nameInput.value !== nameInput.defaultValue);
    }

    isPendingChangesValid(): boolean {
        if (!this.hasPendingChanges()) {
            return true;
        }
        const uriInput = this.#host.view.pageDom.optional('mcp-root-uri-input');
        if (!(uriInput instanceof HTMLInputElement)) {
            return false;
        }
        return Boolean(readTrimmedInputValue(uriInput));
    }

    validatePendingChanges(): boolean {
        if (!this.hasPendingChanges()) {
            return true;
        }
        const uriInput = this.#requireInput('mcp-root-uri-input');
        if (!readTrimmedInputValue(uriInput)) {
            this.#host.view.warnAndFocus(uriInput, i18n.t('settings.mcp.notifications.rootUriRequired'));
            return false;
        }
        return true;
    }

    syncPendingFieldStates(): void {
        const uriInput = this.#host.view.pageDom.optional('mcp-root-uri-input');
        const nameInput = this.#host.view.pageDom.optional('mcp-root-name-input');
        const hasPendingChanges = this.hasPendingChanges();
        if (uriInput instanceof HTMLInputElement) {
            const uriValid = !hasPendingChanges || Boolean(readTrimmedInputValue(uriInput));
            this.#host.execution.syncManualDirtyField('mcp.root.uri', uriInput.value !== uriInput.defaultValue, uriValid);
        } else {
            this.#host.execution.clearManualDirtyField('mcp.root.uri');
        }
        if (nameInput instanceof HTMLInputElement) {
            this.#host.execution.syncManualDirtyField('mcp.root.name', nameInput.value !== nameInput.defaultValue, true);
        } else {
            this.#host.execution.clearManualDirtyField('mcp.root.name');
        }
    }

    renderSubgroup(resolveExpanded: McpSectionExpansionResolver): string {
        const mcpData = this.#host.data.getMcpData();
        const editIndex = this.#host.editing.getMcpRootEditIndex();
        const form = this.#renderRootForm();
        const formTitle = editIndex !== null ? i18n.t('settings.mcp.roots.editTitle') : i18n.t('settings.mcp.roots.form.title');

        return (
            renderMcpCollapsibleSection({
                id: 'roots-form',
                title: formTitle,
                description: i18n.t('settings.mcp.roots.description'),
                className: 'settings-section--mcp settings-section--mcp-roots-form',
                content: form,
                resolveExpanded
            }) +
            renderMcpCollapsibleSection({
                id: 'roots-list',
                title: i18n.t('settings.mcp.roots.listTitle'),
                className: 'settings-section--mcp settings-section--mcp-roots-list',
                content: renderSettingsRecordList({
                    id: UI_IDS.MCP_ROOT_LIST,
                    items: mcpData.roots.map((root, index) => this.#renderRootItem(root, index)),
                    empty: renderEmptyState({ title: i18n.t('settings.mcp.roots.empty'), className: 'ui-empty-state--simple' }).html
                }),
                expanded: mcpData.roots.length > 0,
                resolveExpanded
            })
        );
    }

    async saveRoot(options: { reloadAfterSave?: boolean } = {}): Promise<boolean> {
        let shouldReload = false;
        await this.#host.execution.runWithBoundary('settings:saveMcpRoot', async () => {
            const uriInput = this.#requireInput('mcp-root-uri-input');
            const nameInput = this.#requireInput('mcp-root-name-input');
            const uri = readTrimmedInputValue(uriInput);
            const name = readOptionalTrimmedInputValue(nameInput);

            if (!uri) {
                return this.#host.view.warnAndFocus(uriInput, i18n.t('settings.mcp.notifications.rootUriRequired'));
            }

            const mcpData = this.#host.data.getMcpData();
            const editIndex = this.#host.editing.getMcpRootEditIndex();
            const newRoot: McpRootEntry = { uri, name };
            const roots = [...mcpData.roots];

            if (editIndex !== null && editIndex >= 0 && editIndex < roots.length) {
                roots[editIndex] = newRoot;
            } else {
                roots.push(newRoot);
            }

            await this.#host.services.api.mcp.roots.update({ roots });
            this.#host.execution.feedback.show(i18n.t('settings.mcp.notifications.rootsUpdated'), 'success');

            this.resetRootFormState();
            shouldReload = true;
            if (options.reloadAfterSave !== false) {
                await this.#reload();
            }
        });
        return shouldReload;
    }

    async cancelRootEdit(): Promise<void> {
        this.resetRootFormState();
        await this.#reload();
    }

    startRootEdit(index: number): void {
        const mcpData = this.#host.data.getMcpData();
        const root = mcpData.roots[index];
        if (!root) {
            return;
        }

        this.#host.editing.setMcpRootEditIndex(index);
        this.#rerender();
    }

    async deleteRoot(index: number): Promise<void> {
        const mcpData = this.#host.data.getMcpData();
        const roots = mcpData.roots.filter((_unusedValue, itemIndex) => itemIndex !== index);

        await this.#host.execution.confirmAndExecute(
            'settings:deleteMcpRoot',
            {
                title: i18n.t('settings.mcp.confirmDeleteRoot.title'),
                message: i18n.t('settings.mcp.confirmDeleteRoot.message'),
                confirmText: i18n.t('settings.mcp.roots.actions.delete'),
                cancelText: i18n.t('common.cancel'),
                variant: 'danger'
            },
            () => this.#host.services.api.mcp.roots.update({ roots }),
            i18n.t('settings.mcp.notifications.rootDeleted'),
            async () => {
                await this.#reload();
            },
            null
        );
    }

    resetRootFormState(): void {
        this.#host.editing.setMcpRootEditIndex(null);
    }

    #requireInput(id: string): HTMLInputElement {
        const element = this.#host.view.pageDom.require(id);
        if (!(element instanceof HTMLInputElement)) {
            throw new TypeError(`MCP root form field missing or invalid: ${id}`);
        }
        return element;
    }

    #renderRootForm(): string {
        const sanitizer = this.#host.services.pageContext.sanitizer;
        const mcpData = this.#host.data.getMcpData();
        const editIndex = this.#host.editing.getMcpRootEditIndex();
        const root = editIndex !== null ? mcpData.roots[editIndex] : null;

        const items = [
            renderSettingItem({
                label: i18n.t('settings.mcp.roots.form.uri.label'),
                help: i18n.t('settings.mcp.roots.form.uri.help'),
                fieldKey: createSettingsManualFieldKey('mcp.root.uri'),
                control: `<input type="text" id="mcp-root-uri-input" class="setting-input setting-input--wide" value="${sanitizer.attribute(root?.uri ?? '')}" placeholder="${sanitizer.attribute(i18n.t('settings.mcp.roots.form.uri.placeholder'))}">`
            }),
            renderSettingItem({
                label: i18n.t('settings.mcp.roots.form.name.label'),
                help: i18n.t('settings.mcp.roots.form.name.help'),
                fieldKey: createSettingsManualFieldKey('mcp.root.name'),
                control: `<input type="text" id="mcp-root-name-input" class="setting-input setting-input--wide" value="${sanitizer.attribute(root?.name ?? '')}" placeholder="${sanitizer.attribute(i18n.t('settings.mcp.roots.form.name.placeholder'))}">`
            })
        ];
        const cancelHidden = editIndex !== null ? '' : ' u-hidden';
        const cancelLabel = i18n.t('settings.mcp.roots.actions.cancel');
        const cancelLabelAttr = sanitizer.attribute(cancelLabel);

        return `${renderSettingsGroup(items)}<div class="mcp-form-actions"><button type="button" id="${UI_IDS.MCP_ROOT_CANCEL}" data-action="${MCP_ACTION_ROOT_CANCEL}" class="ui-button ui-button--sm ui-variant-neutral${cancelHidden}" aria-label="${cancelLabelAttr}" data-tooltip="${cancelLabelAttr}">${cancelLabel}</button></div>`;
    }

    #renderRootItem(root: McpRootEntry, index: number): string {
        const sanitizer = this.#host.services.pageContext.sanitizer;
        const info = this.#buildRootInfo(root, sanitizer);
        const actions = this.#buildRootActions(index);
        return `<div class="settings-record-item" data-index="${index}">${info}${actions}</div>`;
    }

    #buildRootInfo(root: McpRootEntry, sanitizer: PageSanitizer): string {
        const nameMarkup = root.name ? `<span class="mcp-root-name">${sanitizer.html(root.name)}</span>` : '';
        return `<div class="settings-record-info mcp-root-info"><span class="settings-record-label mcp-root-uri">${sanitizer.html(root.uri)}</span>${nameMarkup}</div>`;
    }

    #buildRootActions(index: number): string {
        const sanitizer = this.#host.services.pageContext.sanitizer;
        const editLabel = i18n.t('settings.mcp.roots.actions.edit');
        const deleteLabel = i18n.t('settings.mcp.roots.actions.delete');
        const editLabelAttr = sanitizer.attribute(editLabel);
        const deleteLabelAttr = sanitizer.attribute(deleteLabel);
        const editButton = `<button type="button" data-action="${MCP_ACTION_ROOT_EDIT}" class="ui-button ui-button--sm mcp-root-edit-btn" data-index="${index}" aria-label="${editLabelAttr}" data-tooltip="${editLabelAttr}">${editLabel}</button>`;
        const deleteButton = `<button type="button" data-action="${MCP_ACTION_ROOT_DELETE}" class="ui-button ui-button--sm ui-variant-danger mcp-root-delete-btn" data-index="${index}" aria-label="${deleteLabelAttr}" data-tooltip="${deleteLabelAttr}">${deleteLabel}</button>`;
        return `<div class="settings-record-actions mcp-root-actions">${editButton}${deleteButton}</div>`;
    }
}

export { McpRootsManager };
