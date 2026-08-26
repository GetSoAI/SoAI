/* SoAI - Prompts page sections [frontend/assets/ts/pages/prompts/rendering/sections.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { promptsPageConfig } from '@core/routing/pages/collections/collectionPageConfig.ts';
import { buildCollectionSections, buildEmptyState } from '@core/routing/pages/collections/collectionViewBuilders.ts';
import { renderListTable, type ListTableColumn } from '@core/uiprimitives/listTable.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { PROMPTS_ACTION_SELECT_ALL, PROMPTS_ACTION_SORT_LIST } from '@pages/prompts/actions.ts';
import type { SortDirection } from '@core/ui/tables/sortableTable.ts';

const PROMPTS_GRID = promptsPageConfig.grid;
const PROMPT_EMPTY_STATE = PROMPTS_GRID.emptyStateIds.empty;
const PROMPT_FILTERED_EMPTY_STATE = PROMPTS_GRID.emptyStateIds.filtered ?? 'prompts-filtered-empty';

const buildPromptsListColumns = (sortBy: string, sortOrder: SortDirection): readonly ListTableColumn[] => [
    {
        label: i18n.t('prompts.actions.selectAllPrompts'),
        className: 'prompts-list-selection-cell',
        content: uiHtml`<input id="prompts-list-select-all" type="checkbox" data-action="${PROMPTS_ACTION_SELECT_ALL}" aria-label="${i18n.t('prompts.actions.selectAllPrompts')}">`
    },
    { label: i18n.t('prompts.table.prompt'), sortKey: 'name', sortAction: PROMPTS_ACTION_SORT_LIST, active: sortBy === 'name', direction: sortBy === 'name' ? sortOrder : undefined },
    { label: i18n.t('prompts.table.content') },
    { label: i18n.t('prompts.table.updated'), sortKey: 'date', sortAction: PROMPTS_ACTION_SORT_LIST, active: sortBy === 'date', direction: sortBy === 'date' ? sortOrder : undefined },
    { label: i18n.t('common.actions.actions'), className: 'ui-collection-list__header-cell--actions' }
];

const buildPromptsSections = (sortBy: string, sortOrder: SortDirection) => {
    const sections = buildCollectionSections({
        gridId: PROMPTS_GRID.gridId,
        gridClassName: PROMPTS_GRID.gridClassName,
        emptyStates: [
            buildEmptyState({
                id: PROMPT_EMPTY_STATE,
                className: 'prompts-empty ui-collection-list__empty-state',
                icon: { name: 'search', options: { size: 48, strokeWidth: 1.5 } },
                title: i18n.t('prompts.empty.noPromptsYet'),
                description: i18n.t('prompts.empty.createFirst'),
                actions: [
                    {
                        tag: 'button',
                        className: 'ui-button ui-variant-accent',
                        id: 'create-first-prompt',
                        attributes: { 'data-action': 'prompts.createPrompt' },
                        content: i18n.t('prompts.empty.createPromptButton')
                    }
                ]
            }),
            buildEmptyState({
                id: PROMPT_FILTERED_EMPTY_STATE,
                className: 'prompts-empty prompts-filtered-empty ui-collection-list__empty-state',
                icon: { name: 'search', options: { size: 48, strokeWidth: 1.5 } },
                title: i18n.t('search.noResults.title'),
                description: i18n.t('search.noResults.defaultMessage')
            })
        ]
    });
    sections.splice(1, 0, {
        type: 'section',
        tag: 'div',
        id: 'prompts-list-surface',
        className: 'prompts-list-surface ui-collection-list',
        role: 'region',
        children: renderListTable({ tableClassName: 'prompts-list-table', bodyId: 'prompts-list-body', columns: buildPromptsListColumns(sortBy, sortOrder) })
    });
    return sections;
};

export { buildPromptsSections };
