/* SoAI - Prompts page control layer rendering [frontend/assets/ts/pages/prompts/controllers/page/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceItem } from '@core/data/ClientDataHub.ts';
import { toJsonCompatibleValue } from '@core/primitives/clone.ts';
import { renderCollectionGroupEntry } from '@core/collectionpage/collectionGroupEntry.ts';
import type { RefreshSummary } from '@core/collectionpage/publicContracts.ts';
import { i18n } from '@core/i18n/index.ts';
import { setHeaderStatCardSuppressed } from '@core/routing/pages/basepagelayout/headerStats.ts';
import { isArray, isString } from '@core/typeGuards.ts';
import { DEFAULT_GROUP_KEY, PROMPTS_CARD_IDENTITY_ATTRIBUTE } from '@pages/prompts/contracts/constants.ts';
import { isPromptRecord, type PromptRecord } from '@features/prompts/public.ts';
import { type PromptGroup } from '@pages/prompts/contracts/contracts.ts';
import type { PromptsRuntimeContext } from '@pages/prompts/controllers/page/contracts.ts';
import { toPromptResourceItem } from '@pages/prompts/controllers/page/state.ts';

type PromptsPageViewHost = PromptsRuntimeContext;

const normalizePromptCandidate = (item: ResourceItem): PromptRecord | null => {
    const value = toJsonCompatibleValue(item);
    return isPromptRecord(value) ? value : null;
};

const getFilteredPrompts = (host: PromptsPageViewHost): PromptRecord[] => {
    const filtered = host.owners.collections.runtime?.getFiltered?.() ?? null;
    if (!isArray(filtered)) {
        return [];
    }
    const prompts: PromptRecord[] = [];
    for (const item of filtered) {
        const prompt = normalizePromptCandidate(item);
        if (prompt) prompts.push(prompt);
    }
    return prompts;
};

const getAllPrompts = (host: PromptsPageViewHost): PromptRecord[] => {
    const all = host.owners.collections.runtime?.getAll?.() ?? null;
    if (!isArray(all)) {
        return [];
    }
    const prompts: PromptRecord[] = [];
    for (const item of all) {
        const prompt = normalizePromptCandidate(item);
        if (prompt) prompts.push(prompt);
    }
    return prompts;
};

const getFilteredPromptIds = (host: PromptsPageViewHost): readonly string[] => getFilteredPrompts(host).map((prompt) => prompt.id);

const getPromptGroups = (host: PromptsPageViewHost, prompts: PromptRecord[]): PromptGroup[] => {
    const key = host.controls.getSortBy() || DEFAULT_GROUP_KEY;
    const resolvers = host.state.groupResolvers;
    if (!resolvers) {
        return [{ heading: null, prompts }];
    }
    const resolver = key === DEFAULT_GROUP_KEY || key === 'date' || key === 'name' || key === 'color' ? resolvers[key] : resolvers[DEFAULT_GROUP_KEY];
    const grouped = resolver ? resolver(prompts) : [{ heading: null, prompts }];
    return isArray(grouped) ? grouped : [{ heading: null, prompts }];
};

const preparePromptPresentation = (host: PromptsPageViewHost, prompts: PromptRecord[]): string[] => {
    const groupedPrompts = getPromptGroups(host, prompts);
    const resolutions = new Map<string, { key: string; heading: string | null }>();
    for (const [groupIndex, group] of groupedPrompts.entries()) {
        for (const prompt of group.prompts) {
            resolutions.set(prompt.id, { key: String(groupIndex), heading: group.heading });
        }
    }
    const sortBy = host.controls.getSortBy() || DEFAULT_GROUP_KEY;
    return host.state.grouping.applyHeadings({
        items: prompts,
        grouped: sortBy !== DEFAULT_GROUP_KEY,
        firstHeading: host.components.selectionController.isActive() ? i18n.t('prompts.selectionMode') : null,
        resolveItemId: (prompt) => host.operations.getItemCardId(prompt),
        resolveGroup: (prompt) => resolutions.get(prompt.id) ?? { key: null, heading: null }
    });
};

const renderItemCard = (host: PromptsPageViewHost, item: ResourceItem): HTMLElement => {
    const normalized = normalizePromptCandidate(item);
    if (!normalized) {
        throw new TypeError('PromptsPage card item is invalid');
    }
    const card = host.components.cardRenderer.render(normalized, {
        selected: host.components.selectionController.has(normalized.id),
        editing: host.state.editingPromptId === normalized.id
    });
    if (!card) {
        throw new Error('PromptsPage card renderer returned no card');
    }
    host.components.colorToolkit.applyToCard(card, normalized.color);
    return renderCollectionGroupEntry({ card, heading: host.state.grouping.headingFor(String(normalized.id)), identityAttribute: PROMPTS_CARD_IDENTITY_ATTRIBUTE });
};

const renderItemListRow = (host: PromptsPageViewHost, item: ResourceItem): HTMLElement => {
    const normalized = normalizePromptCandidate(item);
    if (!normalized) {
        throw new TypeError('PromptsPage list row item is invalid');
    }
    const row = host.components.listRowRenderer.render(normalized, {
        selected: host.components.selectionController.has(normalized.id)
    });
    if (!row) {
        throw new Error('PromptsPage list row renderer returned no row');
    }
    host.components.colorToolkit.applyToCard(row, normalized.color);
    return row;
};

const renderItems = (host: PromptsPageViewHost): void => {
    const ui = host.state.ui;
    if (!ui || !host.state.cardController) {
        return;
    }
    const filtered = getFilteredPrompts(host);
    const all = getAllPrompts(host);
    host.state.cardController.renderCollection({ filteredItems: filtered.map(toPromptResourceItem), allItems: all.map(toPromptResourceItem) });
    host.owners.pageDom.toggleClass(ui.grid, 'is-grouped', (host.controls.getSortBy() || DEFAULT_GROUP_KEY) !== DEFAULT_GROUP_KEY);
    host.owners.pageDom.toggleClass(ui.grid, 'selection-mode', host.components.selectionController.isActive());
};

const refreshPromptCards = (host: PromptsPageViewHost, ids?: readonly (string | number)[] | null): void => {
    const candidates = ids && ids.length ? ids : getFilteredPrompts(host).map((prompt) => host.operations.getItemCardId(prompt));
    const targetIds = candidates.map((id) => (id == null ? '' : String(id))).filter((id) => Boolean(id));
    if (targetIds.length) {
        host.owners.collections.view?.markDirty?.(targetIds);
    }
};

const updateStats = (host: PromptsPageViewHost): void => {
    const ui = host.state.ui;
    if (!ui) {
        return;
    }
    const stats = host.operations.ensureDataAdapter().computeStats(getAllPrompts(host), host.components.selectionController.size());
    host.owners.pageDom.updateText(ui.totalPromptsValue, String(stats.total));
    host.owners.pageDom.updateText(ui.selectedPromptsValue, String(stats.selectionSize));
    setHeaderStatCardSuppressed({ pageDom: host.owners.pageDom }, ui.selectedPromptsCard, stats.selectionSize <= 0);
    host.owners.pageDom.updateText(ui.totalCharactersValue, i18n.formatNumber(stats.totalCharacters));
    host.owners.pageDom.updateText(ui.specialPromptsValue, String(stats.specialCount));
    host.owners.pageDom.updateText(ui.lastCreatedValue, stats.lastCreatedLabel);
    host.owners.pageDom.updateAttribute(ui.lastCreatedValue, 'data-full-value', stats.lastCreatedLabel);
    host.owners.pageDom.updateAttribute(ui.lastCreatedValue, 'data-compact-value', stats.lastCreatedCompactLabel);
    host.owners.pageDom.updateText(ui.lastModifiedValue, stats.lastModifiedLabel);
    host.owners.pageDom.updateAttribute(ui.lastModifiedValue, 'data-full-value', stats.lastModifiedLabel);
    host.owners.pageDom.updateAttribute(ui.lastModifiedValue, 'data-compact-value', stats.lastModifiedCompactLabel);
    host.owners.layout.applyHeaderStats();
};

const getPromptItemCardId = (item: ResourceItem): string => {
    const identifier = item.id ?? item.name ?? '';
    return identifier ? String(identifier) : '';
};

const getPromptItemSearchFields = (item: ResourceItem): (string | undefined)[] => {
    const contentValue = item['content'];
    const contentText = isString(contentValue) ? contentValue : undefined;
    const nameText = isString(item.name) ? item.name : undefined;
    const idText = item.id === null || item.id === undefined ? undefined : String(item.id);
    return [nameText, contentText, idText];
};

const applyPromptCustomFilters = (): boolean => true;

const onCollectionRefresh = (host: PromptsPageViewHost, summary: RefreshSummary): RefreshSummary => {
    renderItems(host);
    updateStats(host);
    return summary;
};

const renderPromptItem = (host: PromptsPageViewHost, item: ResourceItem): HTMLElement => (host.state.viewMode === 'list' ? renderItemListRow(host, item) : renderItemCard(host, item));

export { applyPromptCustomFilters, getPromptItemCardId, getPromptItemSearchFields, getAllPrompts, getFilteredPromptIds, getFilteredPrompts, getPromptGroups, onCollectionRefresh, preparePromptPresentation, refreshPromptCards, renderPromptItem, renderItemCard, renderItems, updateStats };
export type { PromptsPageViewHost };
