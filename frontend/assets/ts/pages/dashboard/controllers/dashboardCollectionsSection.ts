/* SoAI - Dashboard page collections section [frontend/assets/ts/pages/dashboard/controllers/dashboardCollectionsSection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveCheckerboardClass } from '@core/dom/checkerboardAssignment.ts';
import { narrowHTMLElement } from '@core/dom/narrowElement.ts';
import { i18n } from '@core/i18n/index.ts';
import { normalizeModelRecord } from '@core/models/modelRecordNormalization.ts';
import { resolveModelStatus } from '@core/models/modelStatus.ts';
import { toString, toTrimmedUpper } from '@core/normalize.ts';
import { formatCompactNumber } from '@core/primitives/compactNumber.ts';
import { resolvePluginStatusFromRecord } from '@core/state/pluginStatus.ts';
import { isObject } from '@core/typeGuards.ts';
import { isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import type { DashboardHost } from '@core/edition/dashboardContribution.ts';
import type { StatusManagerContract } from '@pages/dashboard/contracts/statusManager.ts';
import { renderDashboardSectionState } from '@pages/dashboard/controllers/dashboardSectionStateController.ts';
import { pickString } from '@pages/dashboard/state/dashboardStateModel.ts';

type CollectionType = 'plugin' | 'model';

interface CollectionSectionConfig {
    contentId: string;
    dataReady: () => boolean;
    items: () => readonly JsonValue[];
    itemType: CollectionType;
    isCounted: (item: JsonValue) => boolean;
    statusGetter: (item: JsonValue, statusManager: StatusManagerContract | null) => string;
    nameKeys: readonly string[];
    idKeys: readonly string[];
    text: {
        empty: () => string;
        countedLabel: () => string;
        totalLabel: () => string;
        unknownName: () => string;
    };
}

const readJsonCandidate = (value: JsonValue): JsonValue => (isJsonValue(value) ? value : null);

interface DashboardCollectionsRendererDependencies {
    host: DashboardHost;
    getStatusManager: () => StatusManagerContract | null;
    isDestroyed: () => boolean;
}

const toCollection = (value: readonly JsonValue[]): JsonValue[] => value.filter(Boolean);

const createCollectionSectionRenderer = (dependencies: DashboardCollectionsRendererDependencies): ((cfg: CollectionSectionConfig) => void) => {
    const host = dependencies.host;

    return (cfg: CollectionSectionConfig): void => {
        const content = host.requireUI(cfg.contentId);
        const contentElement = narrowHTMLElement(content, `${cfg.itemType} section content`);

        if (!cfg.dataReady()) {
            renderDashboardSectionState(host, contentElement, 'section-loading', i18n.t('common.loading'));
            return;
        }

        const items = cfg.items();
        if (!items.length) {
            renderDashboardSectionState(host, contentElement, 'section-empty', cfg.text.empty());
            return;
        }

        const statusManager = dependencies.getStatusManager();
        const counted = items.filter(cfg.isCounted).length;

        const wrapper = host.createElement('div', { className: `${cfg.itemType}s-overview` });
        const wrapperElement = narrowHTMLElement(wrapper, 'collection wrapper');
        const summary = host.createElement('div', { className: `${cfg.itemType}s-summary dashboard-collection-summary ui-mini-stat-strip` });
        const summaryElement = narrowHTMLElement(summary, 'collection summary');

        const addStat = (value: number, label: string, index: number): void => {
            const stat = host.createElement('div', { className: `${cfg.itemType}-stat ui-mini-stat-strip__card ${resolveCheckerboardClass(index, { columns: 2 })}` });
            const statElement = narrowHTMLElement(stat, 'collection stat');
            const valueNode = host.createElement('span', { className: 'ui-mini-stat-strip__value' }, formatCompactNumber(value));
            const labelNode = host.createElement('span', { className: 'ui-mini-stat-strip__label' }, label);
            statElement.append(narrowHTMLElement(valueNode, 'collection stat value'), narrowHTMLElement(labelNode, 'collection stat label'));
            summaryElement.appendChild(statElement);
        };
        addStat(counted, cfg.text.countedLabel(), 0);
        addStat(items.length, cfg.text.totalLabel(), 1);

        const list = host.createElement('div', { className: `${cfg.itemType}s-list` });
        const listElement = narrowHTMLElement(list, 'collection list');

        items.forEach((item: JsonValue, index: number): void => {
            const itemObject = isObject(item) ? item : {};
            const name = pickString(...cfg.nameKeys.map((key: string): JsonValue => readJsonCandidate(itemObject[key] ?? null))) || cfg.text.unknownName();
            const status = cfg.statusGetter(item, statusManager);
            const label = statusManager?.getDescription(status) || status;
            const row = host.createElement('div', {
                className: `${cfg.itemType}-item ${resolveCheckerboardClass(index)}`
            });
            const rowElement = narrowHTMLElement(row, 'collection row');

            const itemId = pickString(...cfg.idKeys.map((key: string): JsonValue => readJsonCandidate(itemObject[key] ?? null)));
            if (itemId) {
                if (cfg.itemType === 'plugin') {
                    rowElement.dataset['plugin'] = itemId;
                } else {
                    rowElement.dataset['model'] = itemId;
                }
            }

            const nameNode = host.createElement('span', { className: `${cfg.itemType}-name` }, name);
            const nameElement = narrowHTMLElement(nameNode, 'collection name node');
            setTooltipText(nameElement, name);

            const badgeClass = `ui-status-badge ${cfg.itemType === 'model' ? 'model-plugin' : 'plugin-status'}-badge ${statusManager?.getCollectionBadgeClass(status) || 'status-grey'}`;
            const badge = host.createElement('span', { className: badgeClass }, label);
            const badgeElement = narrowHTMLElement(badge, 'collection badge node');
            setTooltipText(badgeElement, label);

            rowElement.append(nameElement, badgeElement);
            listElement.appendChild(rowElement);
        });

        wrapperElement.append(summaryElement, listElement);
        host.replaceElementContent(contentElement, wrapperElement, { escape: false });

        if (dependencies.isDestroyed()) {
            return;
        }
        host.flushDOMUpdates();
    };
};

const getPluginStatus = (plugin: JsonValue, statusManager: StatusManagerContract | null): string => {
    return resolvePluginStatusFromRecord(plugin, statusManager ? (status: JsonValue): string => statusManager.normalizeStatus(status) : undefined);
};

const getModelStatus = (model: JsonValue, statusManager: StatusManagerContract | null): string => {
    const modelRecord = normalizeModelRecord(model);
    return modelRecord ? resolveModelStatus(statusManager, modelRecord) : 'STOPPED';
};

const createDashboardCollectionsRenderers = (dependencies: DashboardCollectionsRendererDependencies): { renderPluginsSection: (items: readonly JsonValue[], dataReady: () => boolean) => void; renderModelsSection: (items: readonly JsonValue[], dataReady: () => boolean) => void } => {
    const renderCollectionSection = createCollectionSectionRenderer(dependencies);
    return {
        renderPluginsSection: (items: readonly JsonValue[], dataReady: () => boolean): void => {
            renderCollectionSection({
                contentId: 'plugins-content',
                dataReady,
                items: () => toCollection(items),
                itemType: 'plugin',
                isCounted: (plugin: JsonValue): boolean => {
                    const pluginObject = isObject(plugin) ? plugin : {};
                    return toTrimmedUpper(toString(pluginObject['state'])) === 'RUNNING';
                },
                statusGetter: (plugin: JsonValue, statusManager: StatusManagerContract | null): string => getPluginStatus(plugin, statusManager),
                nameKeys: ['displayName', 'name'],
                idKeys: ['name'],
                text: {
                    empty: (): string => i18n.t('dashboard.sections.plugins.empty'),
                    countedLabel: (): string => i18n.t('dashboard.sections.plugins.active'),
                    totalLabel: (): string => i18n.t('dashboard.sections.plugins.total'),
                    unknownName: (): string => i18n.t('dashboard.sections.plugins.unknown')
                }
            });
        },
        renderModelsSection: (items: readonly JsonValue[], dataReady: () => boolean): void => {
            renderCollectionSection({
                contentId: 'models-content',
                dataReady,
                items: () => toCollection(items),
                itemType: 'model',
                isCounted: (model: JsonValue): boolean => {
                    const modelObject = isObject(model) ? model : {};
                    return modelObject['state'] === 'LOADED' || Boolean(modelObject['isLoaded']) || Boolean(modelObject['loaded']);
                },
                statusGetter: (model: JsonValue, statusManager: StatusManagerContract | null): string => getModelStatus(model, statusManager),
                nameKeys: ['displayName', 'name'],
                idKeys: ['universalId', 'id', 'name'],
                text: {
                    empty: (): string => i18n.t('dashboard.sections.models.empty'),
                    countedLabel: (): string => i18n.t('dashboard.sections.models.loaded'),
                    totalLabel: (): string => i18n.t('dashboard.sections.models.total'),
                    unknownName: (): string => i18n.t('dashboard.sections.models.unknown')
                }
            });
        }
    };
};

export { createDashboardCollectionsRenderers };
export type { DashboardCollectionsRendererDependencies, StatusManagerContract };
