/* SoAI - Prompts page prompt list row widget [frontend/assets/ts/pages/prompts/rendering/promptListRowWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { serializeElementToHtml } from '@core/dom/html.ts';
import { BaseCardRenderer } from '@core/ui/BaseCardRenderer.ts';
import type { PromptRecord } from '@features/prompts/public.ts';
import { PROMPTS_ACTION_CARD_CANCEL_EDIT, PROMPTS_ACTION_CARD_COPY, PROMPTS_ACTION_CARD_DELETE, PROMPTS_ACTION_CARD_EDIT, PROMPTS_ACTION_CARD_OPEN, PROMPTS_ACTION_CARD_SAVE_EDIT } from '@pages/prompts/actions.ts';
import type { PromptCardHost } from '@pages/prompts/rendering/CardRenderer.ts';

interface PromptListRowContext {
    selected?: boolean | undefined;
    editing?: boolean | undefined;
}

class PromptListRowRenderer extends BaseCardRenderer<PromptRecord | null | undefined, PromptListRowContext> {
    override host: PromptCardHost;

    constructor(options: { host: PromptCardHost }) {
        super({ host: options.host });
        this.host = options.host;
    }

    override render(prompt: PromptRecord | null | undefined, context: PromptListRowContext = {}): HTMLElement | null {
        if (!prompt) {
            return null;
        }
        const selected = Boolean(context.selected);
        const editing = Boolean(context.editing);
        const normalizedColor = this.host.normalizePromptColor(prompt.color) ?? '';
        const openLabel = this.cards.escapeAttribute(prompt.name);
        const className = this.builder.combineClasses('prompts-list-row', selected ? 'is-selected' : '', editing ? 'is-editing' : '');
        const colorAttribute = normalizedColor ? ` data-prompt-color="${this.cards.escapeAttribute(normalizedColor)}"` : '';
        const rowActionAttribute = editing ? '' : ` data-action="${PROMPTS_ACTION_CARD_OPEN}"`;
        const title = editing ? this.renderTitleInput(prompt) : `<button type="button" class="prompts-list-open" data-action="${PROMPTS_ACTION_CARD_OPEN}" aria-label="${openLabel}" data-tooltip="${openLabel}">${this.renderTitleText(prompt)}</button>`;
        const content = editing ? this.renderContentEditor(prompt) : this.renderContentText(prompt);
        const actions = editing ? this.renderEditActions(prompt) : this.renderViewActions();
        const markup = `
            <tr class="${this.cards.escapeAttribute(className)}" data-render-mode="list"${rowActionAttribute} data-prompt-id="${this.cards.escapeAttribute(prompt.id)}" data-selected-color="${this.cards.escapeAttribute(normalizedColor)}"${colorAttribute}>
                <td class="prompts-list-cell prompts-list-selection-cell"><input type="checkbox" aria-label="${openLabel}"${selected ? ' checked' : ''}></td>
                <td class="prompts-list-cell prompts-list-cell-main">
                    ${title}
                </td>
                <td class="prompts-list-cell prompts-list-content">${content}</td>
                <td class="prompts-list-cell prompts-list-updated">${this.renderDate(prompt)}</td>
                <td class="prompts-list-cell prompts-list-actions ui-collection-list__actions">${actions}</td>
            </tr>
        `;
        return this.materializeTableRow(markup);
    }

    renderTitleText(prompt: PromptRecord): string {
        return `<span dir="auto" class="prompts-list-title">${this.cards.escapeHtml(prompt.name)}</span>`;
    }

    renderTitleInput(prompt: PromptRecord): string {
        const label = this.cards.escapeAttribute(i18n.t('prompts.title'));
        const value = this.cards.escapeAttribute(prompt.name);
        return `<input type="text" dir="auto" class="form-input" data-field="name" value="${value}" aria-label="${label}">`;
    }

    renderContentText(prompt: PromptRecord): string {
        return `<span dir="auto" class="prompts-list-preview">${this.cards.escapeHtml(prompt.content)}</span>`;
    }

    renderContentEditor(prompt: PromptRecord): string {
        const label = this.cards.escapeAttribute(i18n.t('prompts.description'));
        return `<textarea dir="auto" class="form-input" data-field="content" aria-label="${label}">${this.cards.escapeHtml(prompt.content)}</textarea>`;
    }

    renderDate(prompt: PromptRecord): string {
        return `<span>${this.cards.escapeHtml(this.host.formatDate(prompt.modifiedAtMs))}</span>`;
    }

    renderViewActions(): string {
        const copyLabel = i18n.t('prompts.actions.copyContent');
        const editLabel = i18n.t('prompts.actions.editPrompt');
        const deleteLabel = i18n.t('prompts.actions.deletePrompt');
        return [this.cards.button({ className: 'ui-round-button ui-round-button--inline ui-round-button--copy', dataset: { action: PROMPTS_ACTION_CARD_COPY, tooltip: copyLabel }, aria: { label: copyLabel }, attributes: { type: 'button' }, icon: { name: 'copy', options: { strokeWidth: 1 } } }), this.cards.button({ className: 'ui-round-button ui-round-button--inline ui-round-button--edit', dataset: { action: PROMPTS_ACTION_CARD_EDIT, tooltip: editLabel }, aria: { label: editLabel }, attributes: { type: 'button' }, icon: { name: 'rename', options: { strokeWidth: 1 } } }), this.cards.button({ className: 'ui-round-button ui-round-button--inline ui-round-button--delete', dataset: { action: PROMPTS_ACTION_CARD_DELETE, tooltip: deleteLabel }, aria: { label: deleteLabel }, attributes: { type: 'button' }, icon: { name: 'close', options: { strokeWidth: 1.5 } } })].join('');
    }

    renderEditActions(prompt: PromptRecord): string {
        return [
            this.cards.button({
                className: 'ui-button ui-button--sm ui-variant-neutral',
                dataset: { action: PROMPTS_ACTION_CARD_CANCEL_EDIT },
                content: this.cards.escapeHtml(i18n.t('common.cancel'))
            }),
            serializeElementToHtml(this.host.renderColorPicker(prompt.color, 'card')),
            this.cards.button({
                className: 'ui-button ui-button--sm ui-variant-accent',
                dataset: { action: PROMPTS_ACTION_CARD_SAVE_EDIT },
                content: this.cards.escapeHtml(i18n.t('prompts.actions.save'))
            })
        ].join('');
    }
}

export { PromptListRowRenderer };
