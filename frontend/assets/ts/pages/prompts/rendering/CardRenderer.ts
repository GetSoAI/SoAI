/* SoAI - Prompts page card renderer [frontend/assets/ts/pages/prompts/rendering/CardRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { serializeElementToHtml } from '@core/dom/html.ts';
import { i18n } from '@core/i18n/index.ts';
import { BaseCardRenderer, type CardRendererHost } from '@core/ui/BaseCardRenderer.ts';
import type { ButtonConfig } from '@core/uiprimitives/public.ts';
import type { PromptRecord } from '@features/prompts/public.ts';
import { PROMPTS_ACTION_CARD_CANCEL_EDIT, PROMPTS_ACTION_CARD_COPY, PROMPTS_ACTION_CARD_DELETE, PROMPTS_ACTION_CARD_EDIT, PROMPTS_ACTION_CARD_OPEN, PROMPTS_ACTION_CARD_SAVE_EDIT } from '@pages/prompts/actions.ts';

interface RenderContext {
    editing?: boolean | undefined;
    selected?: boolean | undefined;
}

interface PromptCardHost extends CardRendererHost {
    normalizePromptColor(color: string | null): string | null;
    formatDate(timestamp: number): string;
    renderColorPicker(color: string | null, context: string): HTMLElement;
}

interface CardRendererOptions {
    host: PromptCardHost;
    fadeThreshold?: number | undefined;
}

class PromptCardRenderer extends BaseCardRenderer<PromptRecord | null | undefined, RenderContext> {
    override host: PromptCardHost;
    fadeThreshold: number;

    constructor(options: CardRendererOptions) {
        super({ host: options.host });
        this.host = options.host;
        const { fadeThreshold = 150 } = options;
        this.fadeThreshold = Number.isFinite(fadeThreshold) && fadeThreshold > 0 ? fadeThreshold : 150;
    }

    override render(prompt: PromptRecord | null | undefined, context: RenderContext = {}): HTMLElement | null {
        if (!prompt) {
            return null;
        }
        const editing = Boolean(context.editing);
        const selected = Boolean(context.selected);
        const className = this.builder.combineClasses('prompt-card', 'prompt-color-surface', selected ? 'is-selected' : '', editing ? 'is-editing' : '');
        const normalizedColor = this.host.normalizePromptColor(prompt.color) ?? '';
        const markup = this.cards.card({
            className,
            includeCollectionRoot: false,
            dataset: {
                action: PROMPTS_ACTION_CARD_OPEN,
                'prompt-id': prompt.id,
                'selected-color': normalizedColor,
                ...(normalizedColor ? { 'prompt-color': normalizedColor } : {})
            },
            actions: this.buildActionButtons(),
            children: [this.buildHeader(prompt, context), this.buildPromptContent(prompt, context), this.buildFooter(prompt, context)]
        });
        const node = this.materialize(toTrustedUiHtml(markup));
        return node instanceof HTMLElement ? node : null;
    }

    override buildActionButtons(): ButtonConfig[] {
        return [
            this.createRoundButton({
                className: 'ui-round-button ui-round-button--delete',
                action: PROMPTS_ACTION_CARD_DELETE,
                iconName: 'close',
                iconOptions: { strokeWidth: 1.5 },
                label: i18n.t('prompts.actions.deletePrompt')
            }),
            this.createRoundButton({
                className: 'ui-round-button ui-round-button--edit',
                action: PROMPTS_ACTION_CARD_EDIT,
                iconName: 'rename',
                iconOptions: { strokeWidth: 1 },
                label: i18n.t('prompts.actions.editPrompt')
            })
        ];
    }

    buildHeader(prompt: PromptRecord, context: RenderContext = {}): string {
        const editing = Boolean(context.editing);
        const titleContent = editing ? this.renderTitleInput(prompt) : this.renderTitleText(prompt);
        return this.cards.section({
            className: 'prompt-card-header',
            children: this.cards.section({
                className: 'prompt-card-title-bar',
                children: this.cards.section({
                    className: 'prompt-card-title',
                    dataset: { 'full-title': prompt.name },
                    children: titleContent
                })
            })
        });
    }

    buildPromptContent(prompt: PromptRecord, context: RenderContext = {}): string {
        const editing = Boolean(context.editing);
        const shouldFade = !editing && this.shouldFadeContent(prompt, context);
        const contentClasses = this.builder.combineClasses('prompt-card-content', shouldFade ? 'fade' : '');
        const textClasses = this.builder.combineClasses('prompt-card-text', shouldFade ? 'fade' : '');
        const textContent = editing ? this.renderTextarea(prompt) : this.renderContentText(prompt);
        return this.cards.section({
            className: contentClasses,
            children: this.cards.section({
                className: textClasses,
                children: textContent
            })
        });
    }

    buildFooter(prompt: PromptRecord, context: RenderContext = {}): string {
        return context.editing ? this.buildEditingFooter(prompt) : this.buildViewFooter(prompt);
    }

    buildEditingFooter(prompt: PromptRecord): string {
        const cancelBtn = this.cards.button({
            className: 'ui-button ui-button--sm ui-variant-neutral',
            dataset: { action: PROMPTS_ACTION_CARD_CANCEL_EDIT },
            content: this.cards.escapeHtml(i18n.t('common.cancel'))
        });
        const saveBtn = this.cards.button({
            className: 'ui-button ui-button--sm ui-variant-accent',
            dataset: { action: PROMPTS_ACTION_CARD_SAVE_EDIT },
            content: this.cards.escapeHtml(i18n.t('prompts.actions.save'))
        });
        const colorPicker = this.renderColorPickerMarkup(prompt.color);
        return this.cards.section({
            className: 'prompt-card-footer prompt-card-save-actions',
            children: `${cancelBtn}${colorPicker}${saveBtn}`
        });
    }

    buildViewFooter(prompt: PromptRecord): string {
        const clockIcon = this.requireCardIcon('clock', { size: 12, strokeWidth: 1.7 });
        const dateLabel = this.cards.escapeHtml(this.host.formatDate(prompt.modifiedAtMs) ?? '');
        const dateRow = this.cards.section({
            className: 'prompt-card-date',
            children: `${clockIcon}<span>${dateLabel}</span>`
        });
        const copyLabel = i18n.t('prompts.actions.copyContent');
        const copyButton = this.cards.button({
            className: 'ui-round-button ui-round-button--inline ui-round-button--copy',
            dataset: { action: PROMPTS_ACTION_CARD_COPY, tooltip: copyLabel },
            aria: { label: copyLabel },
            attributes: { type: 'button' },
            icon: { name: 'copy', options: { strokeWidth: 1 } }
        });
        return this.cards.section({
            className: 'prompt-card-footer',
            children: `${dateRow}${copyButton}`
        });
    }

    shouldFadeContent(prompt: PromptRecord | null | undefined, context: RenderContext): boolean {
        const limit = this.fadeThreshold;
        if (!prompt) {
            return false;
        }
        if (context.editing) {
            return false;
        }
        return prompt.content.length > limit;
    }

    renderTitleInput(prompt: PromptRecord): string {
        const value = this.cards.escapeAttribute(prompt.name);
        return `<input type="text" data-field="name" value="${value}">`;
    }

    renderTitleText(prompt: PromptRecord): string {
        const value = this.cards.escapeHtml(prompt.name);
        return `<span class="prompt-card-title-text">${value}</span>`;
    }

    renderTextarea(prompt: PromptRecord): string {
        const value = this.cards.escapeHtml(prompt.content);
        return `<textarea data-field="content">${value}</textarea>`;
    }

    renderContentText(prompt: PromptRecord): string {
        return this.cards.escapeHtml(prompt.content);
    }

    renderColorPickerMarkup(colorValue: string | null): string {
        const node = this.host.renderColorPicker(colorValue, 'card');
        return serializeElementToHtml(node);
    }
}

export { PromptCardRenderer };
export type { PromptCardHost };
