/* SoAI - Hardware feature network card view [frontend/assets/ts/features/hardware/networkCardView.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { reconcileChildNodes } from '@core/dom/childNodeReconciliation.ts';
import { syncHardwareRowObservationPresentation } from '@features/hardware/rowObservationPresentation.ts';
import type { WindowsNetworkInventoryStatus } from '@core/api/contracts/hardwareContracts.ts';
import { resolveCheckerboardClass } from '@core/dom/checkerboardAssignment.ts';
import { narrowHTMLElement } from '@core/dom/narrowElement.ts';
import { i18n } from '@core/i18n/index.ts';
import { isolateLtrText } from '@core/localization/public.ts';
import { clampPercent } from '@core/primitives/clampNumber.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { formatSpeedValue, netmaskToCidr } from '@features/hardware/Formatters.ts';
import type { HardwareSnapshot, NetworkInterfaceModel } from '@features/hardware/models/types.ts';

interface NetworkCardViewHost {
    createElement: (tagName: string, options?: { className?: string }, text?: string) => Element;
}

interface NetworkCardLabelSet {
    ipv4: string;
    ipv6: string;
    mac: string;
    download: string;
    upload: string;
}

interface NetworkRowOptions {
    host: NetworkCardViewHost;
    entry: NetworkInterfaceModel;
    index: number;
    labels: NetworkCardLabelSet;
}

const FILL_STEP_SIZE = 5;

const formatNetworkInterfaceAddress = (address: NetworkInterfaceModel['primaryAddr'] | null): string => {
    if (!address?.address) {
        return '—';
    }
    const cidr = address.netmask ? `/${netmaskToCidr(address.netmask)}` : '';
    return `${address.address}${cidr}`;
};

const resolveFillStep = (value: number): string => {
    const percent = clampPercent(value);
    if (percent === 0) {
        return '0';
    }
    return String(Math.max(FILL_STEP_SIZE, Math.round(percent / FILL_STEP_SIZE) * FILL_STEP_SIZE));
};

const syncNetworkBarFillData = (fill: HTMLElement, downloadMbps: number | undefined, uploadMbps: number | undefined): void => {
    if (!isFiniteNumber(downloadMbps) || !isFiniteNumber(uploadMbps)) {
        fill.dataset['networkFlow'] = 'idle';
        fill.dataset['fillStep'] = '0';
        return;
    }
    const total = downloadMbps + uploadMbps;
    if (total === 0) {
        fill.dataset['networkFlow'] = 'idle';
        fill.dataset['fillStep'] = '0';
        return;
    }
    fill.dataset['fillStep'] = '100';
    if (uploadMbps === 0) {
        fill.dataset['networkFlow'] = 'download';
        return;
    }
    if (downloadMbps === 0) {
        fill.dataset['networkFlow'] = 'upload';
        return;
    }
    const downloadPercent = (downloadMbps / total) * 100;
    fill.dataset['networkFlow'] = 'mixed';
    fill.dataset['networkMix'] = resolveFillStep(downloadPercent);
};

const createNetworkSpeedSeparator = (host: NetworkCardViewHost): HTMLElement => {
    const separator = narrowHTMLElement(host.createElement('span', { className: 'hardware-network-speed-separator' }, '·'), 'network speed separator');
    separator.setAttribute('aria-hidden', 'true');
    return separator;
};

const createNetworkSpeedContent = (documentRef: Document, speedText: string): HTMLElement => {
    const unitStart = speedText.lastIndexOf(' ') + 1;
    const content = documentRef.createElement('span');
    const unit = documentRef.createElement('span');
    unit.className = 'u-normal-case';
    unit.textContent = speedText.slice(unitStart);
    content.append(documentRef.createTextNode(speedText.slice(0, unitStart)), unit);
    return content;
};

const createNetworkSpeedSegment = (host: NetworkCardViewHost, segmentType: 'download' | 'upload', label: string, value: number | undefined): HTMLElement => {
    const segment = narrowHTMLElement(host.createElement('span', { className: `hardware-network-speed-segment hardware-resource-speed-segment hardware-network-speed-segment--${segmentType}` }), 'network speed segment');
    const arrowClass = segmentType === 'download' ? 'hardware-arrow-download' : 'hardware-arrow-upload';
    const arrow = narrowHTMLElement(host.createElement('span', { className: `hardware-network-speed-arrow ${arrowClass}` }, segmentType === 'download' ? '↓' : '↑'), 'network speed arrow');
    const labelElement = narrowHTMLElement(host.createElement('span', { className: `hardware-network-speed-label hardware-resource-speed-label ${arrowClass}` }, label), 'network speed label');
    const valueElement = narrowHTMLElement(host.createElement('span', { className: 'hardware-network-speed-value' }, isFiniteNumber(value) ? '' : i18n.t('common.notAvailableShort')), 'network speed value');
    valueElement.dir = 'ltr';
    if (isFiniteNumber(value)) {
        valueElement.replaceChildren(createNetworkSpeedContent(valueElement.ownerDocument, formatSpeedValue(value)));
    }
    segment.append(arrow, labelElement, valueElement);
    return segment;
};

const createNetworkSpeedDisplay = (host: NetworkCardViewHost, labels: NetworkCardLabelSet, downloadMbps: number | undefined, uploadMbps: number | null | undefined): HTMLElement => {
    const wrapper = narrowHTMLElement(host.createElement('span', { className: 'hardware-network-speed hardware-resource-value' }), 'network speed display');
    wrapper.append(createNetworkSpeedSegment(host, 'download', labels.download, downloadMbps));
    if (uploadMbps !== null) {
        wrapper.append(createNetworkSpeedSeparator(host), createNetworkSpeedSegment(host, 'upload', labels.upload, uploadMbps));
    }
    return wrapper;
};

const createNetworkStatItem = (host: NetworkCardViewHost, label: string, value: string, truncate: boolean): HTMLElement => {
    const item = narrowHTMLElement(host.createElement('div', { className: 'hardware-network-stat-item hardware-resource-stat-item' }), 'network stat item');
    const labelElement = narrowHTMLElement(host.createElement('span', { className: 'hardware-network-stat-label hardware-resource-stat-label' }, label), 'network stat label');
    const truncatedClass = truncate ? ' hardware-network-stat-value--truncated' : '';
    const valueElement = narrowHTMLElement(host.createElement('span', { className: `hardware-network-stat-value hardware-resource-stat-value hardware-network-stat-value${truncatedClass}` }, value), 'network stat value');
    valueElement.dir = 'ltr';
    if (truncate) {
        setTooltipText(valueElement, value);
    }
    item.append(labelElement, valueElement);
    return item;
};

const createNetworkInterfaceRow = ({ host, entry, index, labels }: NetworkRowOptions): HTMLElement => {
    const rowClasses = [`hardware-network-row hardware-resource-row ${resolveCheckerboardClass(index)}`];
    const row = narrowHTMLElement(host.createElement('div', { className: rowClasses.join(' ') }), 'network row');
    row.dataset['hardwareRowKey'] = entry.deviceId;

    const header = narrowHTMLElement(host.createElement('div', { className: 'hardware-network-row-header hardware-resource-row-header' }), 'network row header');
    const nameElement = narrowHTMLElement(host.createElement('span', { className: 'hardware-network-name hardware-resource-name' }, entry.name), 'network row name');
    nameElement.dir = 'auto';
    setTooltipText(nameElement, entry.name);
    header.append(nameElement, createNetworkSpeedDisplay(host, labels, entry.dlMbps, entry.ulMbps));

    const bar = narrowHTMLElement(host.createElement('div', { className: 'hardware-network-bar progress-bar progress-bar--continuous' }), 'network row bar');
    const barFill = narrowHTMLElement(host.createElement('div', { className: 'hardware-network-bar-fill hardware-resource-bar-fill progress-fill' }), 'network row bar fill');
    syncNetworkBarFillData(barFill, entry.dlMbps, entry.ulMbps);
    bar.appendChild(barFill);

    const stats = narrowHTMLElement(host.createElement('div', { className: 'hardware-network-stats hardware-resource-stats' }), 'network row stats');
    const labelRow = narrowHTMLElement(host.createElement('div', { className: 'hardware-network-stat-row hardware-resource-stat-row' }), 'network row label');
    labelRow.appendChild(narrowHTMLElement(host.createElement('span', undefined, i18n.t('hardware.cards.network.labels.card')), 'network row label text'));
    const statRow = narrowHTMLElement(host.createElement('div', { className: 'hardware-network-stat-row hardware-network-stat-row--triple hardware-resource-stat-row hardware-resource-stat-row--triple' }), 'network row stat row');
    statRow.append(createNetworkStatItem(host, labels.ipv4, formatNetworkInterfaceAddress(entry.primaryAddr), false), createNetworkStatItem(host, labels.ipv6, entry.secondaryAddr?.address ?? '—', true), createNetworkStatItem(host, labels.mac, entry.mac ?? '—', false));
    stats.append(labelRow, statRow);
    row.append(header, bar, stats);
    return row;
};

const syncNetworkObservationPresentation = (container: Element, snapshot: HardwareSnapshot | null | undefined, entries: readonly NetworkInterfaceModel[]): void => {
    const rows = dom.resolveAll('.hardware-network-row', container);
    entries.forEach((entry) => {
        const row = rows.find((candidate) => candidate instanceof HTMLElement && candidate.dataset['hardwareRowKey'] === entry.deviceId);
        if (!(row instanceof HTMLElement)) return;
        syncHardwareRowObservationPresentation(row, entry.observationStatus, snapshot?.capabilities?.monitoringIntervalMs);
    });
};

const buildNetworkEmptyText = (windowsInventoryStatus: WindowsNetworkInventoryStatus | null): string => (windowsInventoryStatus === 'unavailable' ? i18n.t('hardware.cards.network.unavailable') : i18n.t('hardware.cards.network.empty'));

interface NetworkSummaryPresentation {
    text: string;
    speedText: string | null;
    speedStart: number;
}

const resolveNetworkSummaryPresentation = (rows: readonly NetworkInterfaceModel[], windowsInventoryStatus: WindowsNetworkInventoryStatus | null): NetworkSummaryPresentation => {
    if (!rows.length) {
        return { text: windowsInventoryStatus === 'unavailable' ? i18n.t('hardware.cards.network.unavailable') : i18n.t('hardware.cards.network.summary.none'), speedText: null, speedStart: 0 };
    }
    let peakMbps = 0;
    let peakDirection: 'download' | 'upload' | null = null;
    rows.forEach((row) => {
        if (isFiniteNumber(row.dlMbps) && row.dlMbps > peakMbps) {
            peakMbps = row.dlMbps;
            peakDirection = 'download';
        }
        if (isFiniteNumber(row.ulMbps) && row.ulMbps > peakMbps) {
            peakMbps = row.ulMbps;
            peakDirection = 'upload';
        }
    });
    const label = rows.length === 1 ? i18n.t('hardware.cards.network.summary.interfaceSingular') : i18n.t('hardware.cards.network.summary.interfacePlural');
    const direction = peakDirection === 'download' ? i18n.t('hardware.cards.network.summary.peakDownloadMarker') : peakDirection === 'upload' ? i18n.t('hardware.cards.network.summary.peakUploadMarker') : null;
    const hasSpeed = rows.some((row) => isFiniteNumber(row.dlMbps) || isFiniteNumber(row.ulMbps));
    const speedText = hasSpeed ? formatSpeedValue(peakMbps) : null;
    const peak = speedText === null ? i18n.t('common.notAvailableShort') : isolateLtrText(speedText);
    let summary = direction === null ? i18n.t('hardware.cards.network.summary.withPeak', { count: rows.length, label, peakLabel: i18n.t('hardware.cards.network.summary.peakLabel'), peak }) : i18n.t('hardware.cards.network.summary.withPeakDirection', { count: rows.length, label, peakLabel: i18n.t('hardware.cards.network.summary.peakLabel'), peak, direction });
    const peakStart = summary.indexOf(peak);
    if (speedText !== null && peakStart < 0) throw new Error('Network summary is missing its formatted speed');
    const speedStart = speedText === null ? 0 : peakStart + peak.indexOf(speedText);
    const primaryRow = rows.find((row) => (row.dlMbps ?? 0) > 0 || (row.ulMbps ?? 0) > 0);
    if (primaryRow?.name) {
        summary += ` • ${isolateLtrText(primaryRow.name)}`;
    }
    return { text: summary, speedText, speedStart };
};

const buildNetworkSummaryText = (rows: readonly NetworkInterfaceModel[], windowsInventoryStatus: WindowsNetworkInventoryStatus | null = null): string => resolveNetworkSummaryPresentation(rows, windowsInventoryStatus).text;

const syncNetworkSummaryPresentation = (target: Element, rows: readonly NetworkInterfaceModel[], windowsInventoryStatus: WindowsNetworkInventoryStatus | null = null): void => {
    const presentation = resolveNetworkSummaryPresentation(rows, windowsInventoryStatus);
    const documentRef = target.ownerDocument;
    if (presentation.speedText === null) {
        reconcileChildNodes(target, [documentRef.createTextNode(presentation.text)]);
        return;
    }
    const content = documentRef.createElement('span');
    content.append(documentRef.createTextNode(presentation.text.slice(0, presentation.speedStart)), createNetworkSpeedContent(documentRef, presentation.speedText), documentRef.createTextNode(presentation.text.slice(presentation.speedStart + presentation.speedText.length)));
    reconcileChildNodes(target, [content]);
};

export { buildNetworkEmptyText, buildNetworkSummaryText, createNetworkInterfaceRow, syncNetworkObservationPresentation, syncNetworkSummaryPresentation };
export type { NetworkCardLabelSet, NetworkCardViewHost };
