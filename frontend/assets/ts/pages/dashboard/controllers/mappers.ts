/* SoAI - Dashboard page mappers [frontend/assets/ts/pages/dashboard/controllers/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { narrowHTMLElement } from '@core/dom/narrowElement.ts';
import { i18n } from '@core/i18n/index.ts';
import { isObject } from '@core/typeGuards.ts';
import { isJsonObjectMapValue } from '@core/types/runtimeCollectionGuards.ts';
import { buildNetworkInterfaceModels, buildNetworkSummaryText, createNetworkInterfaceRow, DEFAULT_IGNORED_NETWORK_PREFIXES, isHardwareSnapshot, type NetworkCardLabelSet, type NetworkInterfaceModel } from '@features/hardware/public.ts';
import type { DashboardHardwareSectionsRenderContext } from '@pages/dashboard/controllers/contracts.ts';
import { syncKeyedList, type KeyedListRow } from '@pages/dashboard/controllers/effects.ts';

const getNetworkLabels = (): NetworkCardLabelSet => ({
    ipv4: i18n.t('hardware.cards.network.labels.ipv4'),
    ipv6: i18n.t('hardware.cards.network.labels.ipv6'),
    mac: i18n.t('hardware.cards.network.labels.mac'),
    download: i18n.t('hardware.cards.network.labels.download'),
    upload: i18n.t('hardware.cards.network.labels.upload')
});

const syncNetworkSummary = (host: DashboardHardwareSectionsRenderContext['host'], rows: readonly NetworkInterfaceModel[]): void => {
    const summary = host.optionalHTMLElement('#dashboardNetworkSummary');
    if (summary) {
        summary.textContent = buildNetworkSummaryText(rows);
    }
};

export const renderNetworkInterfacesSection = ({ host, state, isDestroyed }: DashboardHardwareSectionsRenderContext): void => {
    if (isDestroyed()) {
        return;
    }

    const content = host.requireUI('network-content');
    const contentElement = narrowHTMLElement(content, 'network content');

    if (!state.hasHardware()) {
        const loadingNode = host.createElement('div', { className: 'hardware-network-placeholder u-text-muted' }, i18n.t('hardware.cards.network.waiting'));
        host.replaceElementContent(contentElement, narrowHTMLElement(loadingNode, 'network loading node'), { escape: false });
        syncNetworkSummary(host, []);
        host.flushDOMUpdates();
        return;
    }

    const snapshot = state.getRawHardwareSnapshot();
    const liveSpeedSnapshot = isObject(snapshot) ? snapshot.networkSpeed : null;
    const speeds = isJsonObjectMapValue(liveSpeedSnapshot) ? liveSpeedSnapshot : undefined;
    const rows = buildNetworkInterfaceModels(isHardwareSnapshot(snapshot) ? snapshot : undefined, {
        speeds,
        ignorePrefixes: DEFAULT_IGNORED_NETWORK_PREFIXES
    });

    if (!rows.length) {
        const emptyNode = host.createElement('div', { className: 'hardware-network-empty u-text-muted' }, i18n.t('hardware.cards.network.empty'));
        host.replaceElementContent(contentElement, narrowHTMLElement(emptyNode, 'network empty node'), { escape: false });
        syncNetworkSummary(host, []);
        host.flushDOMUpdates();
        return;
    }

    const keyedRows: KeyedListRow<NetworkInterfaceModel>[] = rows.map((entry) => ({
        key: entry.deviceId,
        signature: [entry.name, entry.dlMbps, entry.ulMbps, entry.primaryAddr?.address ?? '', entry.primaryAddr?.netmask ?? '', entry.secondaryAddr?.address ?? '', entry.mac ?? ''].join('|'),
        value: entry
    }));
    const labels = getNetworkLabels();
    syncKeyedList({
        content: contentElement,
        listClassName: 'hardware-network-list',
        rows: keyedRows,
        createList: () => narrowHTMLElement(host.createElement('div', { className: 'hardware-network-list' }), 'network interface list'),
        createRow: (entry, index) => createNetworkInterfaceRow({ host, entry, index, labels })
    });
    syncNetworkSummary(host, rows);
    host.flushDOMUpdates();
};
