/* SoAI - Hardware feature storage card view [frontend/assets/ts/features/hardware/storageCardView.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isHardwareObservationFresh } from '@core/api/contracts/hardwareComponentObservationContracts.ts';
import { syncHardwareRowObservationPresentation } from '@features/hardware/rowObservationPresentation.ts';
import { resolveCheckerboardClass } from '@core/dom/checkerboardAssignment.ts';
import { narrowHTMLElement } from '@core/dom/narrowElement.ts';
import { i18n } from '@core/i18n/index.ts';
import { isolateLtrText } from '@core/localization/public.ts';
import { formatGigabytesAsStorageUnit } from '@core/primitives/byteSize.ts';
import { clampPercent } from '@core/primitives/clampNumber.ts';
import { formatPercent } from '@core/primitives/percent.ts';
import { isNullOrUndefined } from '@core/typeGuards.ts';
import { resolveProgressColor } from '@core/ui/progressColors.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import type { HardwareSnapshot, VolumeModel } from '@features/hardware/models/types.ts';

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
    valueElement.dir = 'ltr';
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
    const progressColor = resolveProgressColor(volume.percentUsed, 'usage');
    const rowClasses = [`hardware-storage-row hardware-resource-row ${resolveCheckerboardClass(index)}`];
    const row = narrowHTMLElement(host.createElement('div', { className: rowClasses.join(' ') }), 'storage row');
    row.dataset['hardwareRowKey'] = `${volume.deviceId}|${volume.mount}`;

    const header = narrowHTMLElement(host.createElement('div', { className: 'hardware-storage-row-header hardware-resource-row-header' }), 'storage row header');
    const nameElement = narrowHTMLElement(host.createElement('span', { className: 'hardware-storage-name hardware-resource-name' }, volume.filesystem), 'storage row name');
    nameElement.dir = 'ltr';
    setTooltipText(nameElement, volume.filesystem);
    const usageElement = narrowHTMLElement(host.createElement('span', { className: 'hardware-storage-usage hardware-resource-value' }, formatPercent(volume.percentUsed)), 'storage row usage');
    dom.setStyle(usageElement, '--soai-progress-color', progressColor);
    header.append(nameElement, usageElement);

    const bar = narrowHTMLElement(host.createElement('div', { className: 'hardware-storage-bar progress-bar progress-bar--continuous' }), 'storage row bar');
    const fill = narrowHTMLElement(host.createElement('div', { className: 'hardware-resource-bar-fill progress-fill' }), 'storage row bar fill');
    dom.setStyle(fill, '--soai-progress-color', progressColor);
    fill.dataset['fillStep'] = resolveFillStep(volume.percentUsed);
    bar.appendChild(fill);

    const stats = narrowHTMLElement(host.createElement('div', { className: 'hardware-storage-stats hardware-resource-stats' }), 'storage row stats');
    const primaryRow = narrowHTMLElement(host.createElement('div', { className: 'hardware-storage-stat-row hardware-resource-stat-row' }), 'storage row primary');
    const mount = narrowHTMLElement(host.createElement('span'), 'storage row mount');
    const mountValue = narrowHTMLElement(host.createElement('bdi', undefined, volume.mount), 'storage row mount value');
    mountValue.dir = 'ltr';
    mount.append(narrowHTMLElement(host.createElement('strong', undefined, `${labels.mount}: `), 'storage row mount label'), mountValue);
    const type = narrowHTMLElement(host.createElement('span'), 'storage row type');
    type.append(narrowHTMLElement(host.createElement('strong', undefined, `${labels.type}: `), 'storage row type label'), narrowHTMLElement(host.createElement('span', undefined, volume.fstype), 'storage row type value'));
    primaryRow.append(mount, type);

    const tripleRow = narrowHTMLElement(host.createElement('div', { className: 'hardware-storage-stat-row hardware-storage-stat-row--triple hardware-resource-stat-row hardware-resource-stat-row--triple' }), 'storage row triple');
    tripleRow.append(createStorageStatItem(host, labels.used, formatStorageStatValue(volume.used)), createStorageStatItem(host, labels.available, formatStorageStatValue(volume.available)), createStorageStatItem(host, labels.total, formatStorageStatValue(volume.size)));
    stats.append(primaryRow, tripleRow);
    row.append(header, bar, stats);
    return row;
};

const syncStorageObservationPresentation = (container: Element, snapshot: HardwareSnapshot | null | undefined, volumes: readonly VolumeModel[]): void => {
    const rows = dom.resolveAll('.hardware-storage-row', container);
    volumes.forEach((volume) => {
        const row = rows.find((entry) => entry instanceof HTMLElement && entry.dataset['hardwareRowKey'] === `${volume.deviceId}|${volume.mount}`);
        if (!(row instanceof HTMLElement)) return;
        syncHardwareRowObservationPresentation(row, volume.observationStatus, snapshot?.capabilities?.monitoringIntervalMs);
    });
};

const isStorageUnavailable = (snapshot: HardwareSnapshot | null | undefined): boolean => {
    const status = snapshot?.componentStatus?.['disk'];
    return status !== undefined && (!isHardwareObservationFresh(status) || (status.status === 'partial' && !snapshot?.disk?.some((volume) => volume.totalBytes !== undefined)));
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
        total: isolateLtrText(formatGigabytesAsStorageUnit(totalSizeGb, 2))
    });
};

export { buildStorageSummaryText, createStorageInterfaceRow, syncStorageObservationPresentation, isStorageUnavailable };
export type { StorageCardLabelSet, StorageCardViewHost };
