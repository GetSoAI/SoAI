/* SoAI - Hardware feature network card view [frontend/assets/ts/features/hardware/networkCardView.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveCheckerboardClass } from '@core/dom/checkerboardAssignment.ts';
import { narrowHTMLElement } from '@core/dom/narrowElement.ts';
import { i18n } from '@core/i18n/index.ts';
import { clampPercent } from '@core/primitives/clampNumber.ts';
import { isNullOrUndefined } from '@core/typeGuards.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { formatSpeedValue, netmaskToCidr } from '@features/hardware/Formatters.ts';
import type { NetworkInterfaceModel } from '@features/hardware/models/types.ts';

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

const syncNetworkBarFillData = (fill: HTMLElement, downloadMbps: number, uploadMbps: number): void => {
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

const createNetworkSpeedSegment = (host: NetworkCardViewHost, segmentType: 'download' | 'upload', label: string, value: number): HTMLElement => {
    const segment = narrowHTMLElement(host.createElement('span', { className: `hardware-network-speed-segment hardware-resource-speed-segment hardware-network-speed-segment--${segmentType}` }), 'network speed segment');
    const arrowClass = segmentType === 'download' ? 'hardware-arrow-download' : 'hardware-arrow-upload';
    const arrow = narrowHTMLElement(host.createElement('span', { className: `hardware-network-speed-arrow ${arrowClass}` }, segmentType === 'download' ? '↓' : '↑'), 'network speed arrow');
    const labelElement = narrowHTMLElement(host.createElement('span', { className: `hardware-network-speed-label hardware-resource-speed-label ${arrowClass}` }, label), 'network speed label');
    const valueElement = narrowHTMLElement(host.createElement('span', { className: 'hardware-network-speed-value' }, formatSpeedValue(value)), 'network speed value');
    segment.append(arrow, labelElement, valueElement);
    return segment;
};

const createNetworkSpeedDisplay = (host: NetworkCardViewHost, labels: NetworkCardLabelSet, downloadMbps: number, uploadMbps: number | null): HTMLElement => {
    const wrapper = narrowHTMLElement(host.createElement('span', { className: 'hardware-network-speed hardware-resource-value' }), 'network speed display');
    wrapper.append(createNetworkSpeedSegment(host, 'download', labels.download, downloadMbps));
    if (!isNullOrUndefined(uploadMbps)) {
        wrapper.append(createNetworkSpeedSeparator(host), createNetworkSpeedSegment(host, 'upload', labels.upload, uploadMbps));
    }
    return wrapper;
};

const createNetworkStatItem = (host: NetworkCardViewHost, label: string, value: string, truncate: boolean): HTMLElement => {
    const item = narrowHTMLElement(host.createElement('div', { className: 'hardware-network-stat-item hardware-resource-stat-item' }), 'network stat item');
    const labelElement = narrowHTMLElement(host.createElement('span', { className: 'hardware-network-stat-label hardware-resource-stat-label' }, label), 'network stat label');
    const truncatedClass = truncate ? ' hardware-network-stat-value--truncated' : '';
    const valueElement = narrowHTMLElement(host.createElement('span', { className: `hardware-network-stat-value hardware-resource-stat-value hardware-network-stat-value${truncatedClass}` }, value), 'network stat value');
    if (truncate) {
        setTooltipText(valueElement, value);
    }
    item.append(labelElement, valueElement);
    return item;
};

const createNetworkInterfaceRow = ({ host, entry, index, labels }: NetworkRowOptions): HTMLElement => {
    const rowClasses = [`hardware-network-row hardware-resource-row ${resolveCheckerboardClass(index)}`];
    const row = narrowHTMLElement(host.createElement('div', { className: rowClasses.join(' ') }), 'network row');

    const header = narrowHTMLElement(host.createElement('div', { className: 'hardware-network-row-header hardware-resource-row-header' }), 'network row header');
    const nameElement = narrowHTMLElement(host.createElement('span', { className: 'hardware-network-name hardware-resource-name' }, entry.name), 'network row name');
    setTooltipText(nameElement, entry.name);
    header.append(nameElement, createNetworkSpeedDisplay(host, labels, entry.dlMbps, entry.ulMbps));

    const bar = narrowHTMLElement(host.createElement('div', { className: 'hardware-network-bar hardware-resource-bar' }), 'network row bar');
    const barFill = narrowHTMLElement(host.createElement('div', { className: 'hardware-network-bar-fill hardware-resource-bar-fill' }), 'network row bar fill');
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

const buildNetworkSummaryText = (rows: readonly NetworkInterfaceModel[]): string => {
    if (!rows.length) {
        return i18n.t('hardware.cards.network.summary.none');
    }
    let peakMbps = 0;
    let peakDirection: 'download' | 'upload' | null = null;
    rows.forEach((row) => {
        if (row.dlMbps > peakMbps) {
            peakMbps = row.dlMbps;
            peakDirection = 'download';
        }
        if (row.ulMbps > peakMbps) {
            peakMbps = row.ulMbps;
            peakDirection = 'upload';
        }
    });
    const label = rows.length === 1 ? i18n.t('hardware.cards.network.summary.interfaceSingular') : i18n.t('hardware.cards.network.summary.interfacePlural');
    const direction = peakDirection === 'download' ? i18n.t('hardware.cards.network.summary.peakDownloadMarker') : peakDirection === 'upload' ? i18n.t('hardware.cards.network.summary.peakUploadMarker') : null;
    let summary = direction === null ? i18n.t('hardware.cards.network.summary.withPeak', { count: rows.length, label, peakLabel: i18n.t('hardware.cards.network.summary.peakLabel'), peak: formatSpeedValue(peakMbps) }) : i18n.t('hardware.cards.network.summary.withPeakDirection', { count: rows.length, label, peakLabel: i18n.t('hardware.cards.network.summary.peakLabel'), peak: formatSpeedValue(peakMbps), direction });
    const primaryRow = rows.find((row) => row.dlMbps > 0 || row.ulMbps > 0);
    if (primaryRow?.name) {
        summary += ` • ${primaryRow.name}`;
    }
    return summary;
};

export { buildNetworkSummaryText, createNetworkInterfaceRow };
export type { NetworkCardLabelSet, NetworkCardViewHost };
