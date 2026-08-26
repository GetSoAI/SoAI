/* SoAI - Prompts page header [frontend/assets/ts/pages/prompts/rendering/header.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { buildCardGridHeader } from '@core/routing/pages/collections/collectionViewBuilders.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { renderSortControl } from '@core/uiprimitives/sortableList.ts';
import type { SortDirection } from '@core/ui/tables/sortableTable.ts';
import { PROMPTS_ACTION_TOGGLE_VIEW_MODE } from '@pages/prompts/actions.ts';
import { createPromptsSortControlDefinition, normalizePromptsSortState } from '@pages/prompts/controllers/page/listSortingController.ts';
import type { PromptsGetIconSync } from '@pages/prompts/rendering/internalContracts.ts';

const withDataAction = (action: string): Record<string, string> => ({ 'data-action': action });

const buildPromptsHeader = (getIconSync: PromptsGetIconSync, sortBy: string, sortOrder: SortDirection) => {
    return buildCardGridHeader({
        containerClass: 'prompts-container collections-page page-scrollable',
        title: i18n.t('prompts.title'),
        description: i18n.t('prompts.description'),
        actions: [
            { type: 'search' },
            { type: 'custom', html: renderSortControl(createPromptsSortControlDefinition(normalizePromptsSortState({ sortBy, sortOrder }))) },
            {
                type: 'button',
                content: uiHtml`${getIconSync('dashboard', { size: 24, strokeWidth: 1.5 })}<span>${i18n.t('common.actions.cardView')}</span>`,
                variant: 'ui-variant-neutral',
                id: 'prompts-view-mode-toggle',
                ariaLabel: i18n.t('common.actions.cardView'),
                attributes: { 'data-action': PROMPTS_ACTION_TOGGLE_VIEW_MODE, 'aria-pressed': 'false' }
            },
            {
                type: 'button',
                content: uiHtml`${getIconSync('select', { size: 24, strokeWidth: 1.5 })}<span>${i18n.t('prompts.actions.selectAll')}</span>`,
                id: 'select-all',
                ariaLabel: i18n.t('prompts.actions.selectAllPrompts'),
                class: 'u-hidden',
                attributes: withDataAction('prompts.selectAll')
            },
            {
                type: 'button',
                content: uiHtml`${getIconSync('close', { size: 24, strokeWidth: 1.5 })}<span>${i18n.t('prompts.actions.deselectAll')}</span>`,
                id: 'deselect-all',
                ariaLabel: i18n.t('prompts.actions.deselectAllPrompts'),
                class: 'u-hidden',
                attributes: withDataAction('prompts.deselectAll')
            },
            {
                type: 'button',
                content: uiHtml`<span class="toggle-selection-mode-open-icon" aria-hidden="true">${getIconSync('select', { size: 24, strokeWidth: 1.5 })}</span><span class="toggle-selection-mode-label">${i18n.t('prompts.actions.selectionToggleLabel')}</span><span class="toggle-selection-mode-close-icon" aria-hidden="true">${getIconSync('close', { size: 24, strokeWidth: 1.5 })}</span>`,
                id: 'toggle-selection-mode',
                ariaLabel: i18n.t('prompts.actions.toggleSelection'),
                class: 'toggle-selection-mode',
                attributes: withDataAction('prompts.toggleSelectionMode')
            },
            {
                type: 'button',
                content: uiHtml`${getIconSync('add', { size: 24, strokeWidth: 1.5 })}<span>${i18n.t('prompts.actions.addPromptButton')}</span>`,
                variant: 'ui-variant-accent',
                id: 'create-prompt',
                ariaLabel: i18n.t('prompts.actions.createPrompt'),
                class: 'create-prompt',
                attributes: withDataAction('prompts.createPrompt')
            },
            {
                type: 'button',
                content: uiHtml`${getIconSync('copy', { size: 24, strokeWidth: 1.5 })}<span class="prompts-batch-action-label">${i18n.t('prompts.actions.duplicate')}</span>`,
                variant: 'ui-variant-neutral',
                id: 'duplicate-selected',
                ariaLabel: i18n.t('prompts.actions.duplicateSelected'),
                class: 'u-hidden',
                attributes: withDataAction('prompts.duplicateSelected')
            },
            {
                type: 'button',
                content: uiHtml`${getIconSync('download', { size: 24, strokeWidth: 1.5 })}<span class="prompts-batch-action-label">${i18n.t('prompts.actions.download')}</span>`,
                variant: 'ui-variant-accent',
                id: 'download-selected',
                ariaLabel: i18n.t('prompts.actions.downloadSelected'),
                class: 'u-hidden',
                attributes: withDataAction('prompts.downloadSelected')
            },
            {
                type: 'button',
                content: uiHtml`${getIconSync('delete', { size: 24, strokeWidth: 1.5 })}<span class="prompts-batch-action-label">${i18n.t('prompts.actions.delete')}</span>`,
                variant: 'ui-variant-danger',
                id: 'delete-selected',
                ariaLabel: i18n.t('prompts.actions.deleteSelected'),
                class: 'u-hidden',
                attributes: withDataAction('prompts.deleteSelected')
            }
        ],
        stats: [
            { id: 'total-prompts', label: i18n.t('prompts.stats.totalPrompts') },
            { id: 'special-prompts', label: i18n.t('prompts.stats.specialPrompts') },
            { id: 'total-characters', label: i18n.t('prompts.stats.totalCharacters') },
            { id: 'last-created', label: i18n.t('prompts.stats.lastCreated') },
            { id: 'last-modified', label: i18n.t('prompts.stats.last_modified') },
            { id: 'selected-prompts', label: i18n.t('prompts.stats.selected') }
        ]
    });
};

export { buildPromptsHeader };
