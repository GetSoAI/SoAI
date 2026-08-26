/* SoAI - Hardware feature storage card view [frontend/assets/ts/features/hardware/storageCardView.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveCheckerboardClass } from '@core/dom/checkerboardAssignment.ts';
import { narrowHTMLElement } from '@core/dom/narrowElement.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatGigabytesAsStorageUnit } from '@core/primitives/byteSize.ts';
import { clampPercent } from '@core/primitives/clampNumber.ts';
import { formatPercent } from '@core/primitives/percent.ts';
import { isNullOrUndefined } from '@core/typeGuards.ts';
import { resolveProgressUsageClass } from '@core/ui/progressWidths.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import type { VolumeModel } from '@features/hardware/models/types.ts';

interface StorageCardViewHost {
    createElement: (tagName: string, options?: { className?: string }, text?: string) => Element;
}

interface StorageCardLabelSet {
    mount: string;
    type: string;
    used: string;
    available: string;
    total: string;
}

interface StorageRowOptions {
    host: StorageCardViewHost;
    volume: VolumeModel;
    index: number;
    labels: StorageCardLabelSet;
}

const FILL_STEP_SIZE = 5;

const formatStorageStatValue = (value: string | number | null | undefined): string => {
    if (isNullOrUndefined(value)) {
        return '—';
    }
    if (typeof value === 'number') {
        return Number.isFinite(value) ? String(value) : '—';
    }
    const text = String(value).trim();
    return text ? text : '—';
};

const createStorageStatItem = (host: StorageCardViewHost, label: string, value: string): HTMLElement => {
    const item = narrowHTMLElement(host.createElement('div', { className: 'hardware-storage-stat-item hardware-resource-stat-item' }), 'storage stat item');
    const labelElement = narrowHTMLElement(host.createElement('span', { className: 'hardware-storage-stat-label hardware-resource-stat-label' }, label), 'storage stat label');
    const valueElement = narrowHTMLElement(host.createElement('span', { className: 'hardware-storage-stat-value hardware-resource-stat-value' }, value), 'storage stat value');
    item.append(labelElement, valueElement);
    return item;
};

const resolveFillStep = (value: number): string => {
    const percent = clampPercent(value);
    if (percent === 0) {
        return '0';
    }
    return String(Math.max(FILL_STEP_SIZE, Math.round(percent / FILL_STEP_SIZE) * FILL_STEP_SIZE));
};

const createStorageInterfaceRow = ({ host, volume, index, labels }: StorageRowOptions): HTMLElement => {
    const usageClass = resolveProgressUsageClass(volume.percentUsed);
    const rowClasses = [`hardware-storage-row hardware-resource-row ${resolveCheckerboardClass(index)}`];
    const row = narrowHTMLElement(host.createElement('div', { className: rowClasses.join(' ') }), 'storage row');

    const header = narrowHTMLElement(host.createElement('div', { className: 'hardware-storage-row-header hardware-resource-row-header' }), 'storage row header');
    const nameElement = narrowHTMLElement(host.createElement('span', { className: 'hardware-storage-name hardware-resource-name' }, volume.filesystem), 'storage row name');
    setTooltipText(nameElement, volume.filesystem);
    const usageElement = narrowHTMLElement(host.createElement('span', { className: `hardware-storage-usage hardware-resource-value progress-value--inverted ${usageClass}` }, formatPercent(volume.percentUsed)), 'storage row usage');
    header.append(nameElement, usageElement);

    const bar = narrowHTMLElement(host.createElement('div', { className: 'hardware-storage-bar hardware-resource-bar progress-bar--inverted' }), 'storage row bar');
    const fill = narrowHTMLElement(host.createElement('div', { className: `hardware-resource-bar-fill ${usageClass}` }), 'storage row bar fill');
    fill.dataset['fillStep'] = resolveFillStep(volume.percentUsed);
    bar.appendChild(fill);

    const stats = narrowHTMLElement(host.createElement('div', { className: 'hardware-storage-stats hardware-resource-stats' }), 'storage row stats');
    const primaryRow = narrowHTMLElement(host.createElement('div', { className: 'hardware-storage-stat-row hardware-resource-stat-row' }), 'storage row primary');
    const mount = narrowHTMLElement(host.createElement('span'), 'storage row mount');
    mount.append(narrowHTMLElement(host.createElement('strong', undefined, `${labels.mount}: `), 'storage row mount label'), narrowHTMLElement(host.createElement('span', undefined, volume.mount), 'storage row mount value'));
    const type = narrowHTMLElement(host.createElement('span'), 'storage row type');
    type.append(narrowHTMLElement(host.createElement('strong', undefined, `${labels.type}: `), 'storage row type label'), narrowHTMLElement(host.createElement('span', undefined, volume.fstype), 'storage row type value'));
    primaryRow.append(mount, type);

    const tripleRow = narrowHTMLElement(host.createElement('div', { className: 'hardware-storage-stat-row hardware-storage-stat-row--triple hardware-resource-stat-row hardware-resource-stat-row--triple' }), 'storage row triple');
    tripleRow.append(createStorageStatItem(host, labels.used, formatStorageStatValue(volume.used)), createStorageStatItem(host, labels.available, formatStorageStatValue(volume.available)), createStorageStatItem(host, labels.total, formatStorageStatValue(volume.size)));
    stats.append(primaryRow, tripleRow);
    row.append(header, bar, stats);
    return row;
};

const buildStorageSummaryText = (volumes: readonly VolumeModel[]): string => {
    if (!volumes.length) {
        return i18n.t('hardware.cards.storage.summary.none');
    }
    const totalSizeGb = volumes.reduce((sum, entry) => sum + entry.sizeGb, 0);
    const label = volumes.length === 1 ? i18n.t('hardware.cards.storage.summary.volumeSingular') : i18n.t('hardware.cards.storage.summary.volumePlural');
    return i18n.t('hardware.cards.storage.summary.withTotal', {
        count: volumes.length,
        label,
        total: formatGigabytesAsStorageUnit(totalSizeGb, 2)
    });
};

export { buildStorageSummaryText, createStorageInterfaceRow };
export type { StorageCardLabelSet, StorageCardViewHost };
