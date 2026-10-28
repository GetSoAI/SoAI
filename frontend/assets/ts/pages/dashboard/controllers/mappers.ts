/* SoAI - Dashboard page mappers [frontend/assets/ts/pages/dashboard/controllers/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import type { WindowsNetworkInventoryStatus } from '@core/api/contracts/hardwareContracts.ts';
import { narrowHTMLElement } from '@core/dom/narrowElement.ts';
import { i18n } from '@core/i18n/index.ts';
import { isObject } from '@core/typeGuards.ts';
import { isJsonObjectMapValue } from '@core/types/runtimeCollectionGuards.ts';
import { buildNetworkEmptyText, buildNetworkInterfaceModels, syncNetworkSummaryPresentation, createNetworkInterfaceRow, syncNetworkObservationPresentation, DEFAULT_IGNORED_NETWORK_PREFIXES, getWindowsNetworkInventoryStatus, isHardwareSnapshot, type NetworkCardLabelSet, type NetworkInterfaceModel } from '@features/hardware/public.ts';
import type { DashboardHardwareSectionsRenderContext } from '@pages/dashboard/controllers/contracts.ts';
import { syncKeyedList, type KeyedListRow } from '@pages/dashboard/controllers/effects.ts';

const getNetworkLabels = (): NetworkCardLabelSet => ({
    ipv4: i18n.t('hardware.cards.network.labels.ipv4'),
    ipv6: i18n.t('hardware.cards.network.labels.ipv6'),
    mac: i18n.t('hardware.cards.network.labels.mac'),
    download: i18n.t('hardware.cards.network.labels.download'),
    upload: i18n.t('hardware.cards.network.labels.upload')
});

const syncNetworkSummary = (host: DashboardHardwareSectionsRenderContext['host'], rows: readonly NetworkInterfaceModel[], windowsInventoryStatus: WindowsNetworkInventoryStatus | null = null): void => {
    const summary = host.optionalHTMLElement('#dashboardNetworkSummary');
    if (summary) {
        syncNetworkSummaryPresentation(summary, rows, windowsInventoryStatus);
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
    const hardwareSnapshot = isHardwareSnapshot(snapshot) ? snapshot : undefined;
    const rows = buildNetworkInterfaceModels(hardwareSnapshot, {
        speeds,
        ignorePrefixes: DEFAULT_IGNORED_NETWORK_PREFIXES
    });

    if (!rows.length) {
        const windowsInventoryStatus = getWindowsNetworkInventoryStatus(hardwareSnapshot);
        const emptyNode = host.createElement('div', { className: 'hardware-network-empty u-text-muted' }, buildNetworkEmptyText(windowsInventoryStatus));
        host.replaceElementContent(contentElement, narrowHTMLElement(emptyNode, 'network empty node'), { escape: false });
        syncNetworkSummary(host, [], windowsInventoryStatus);
        host.flushDOMUpdates();
        return;
    }

    const keyedRows: KeyedListRow<NetworkInterfaceModel>[] = rows.map((entry) => ({
        key: entry.deviceId,
        signature: [entry.name, entry.dlMbps, entry.ulMbps, entry.primaryAddr?.address ?? '', entry.primaryAddr?.netmask ?? '', entry.secondaryAddr?.address ?? '', entry.mac ?? '', JSON.stringify(entry.observationStatus)].join('|'),
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
    const orderedRows = dom
        .resolveAll('.hardware-network-row', contentElement)
        .map((row) => rows.find((entry) => entry.deviceId === (row instanceof HTMLElement ? row.dataset['dashboardRowKey'] : null)))
        .filter((entry): entry is NetworkInterfaceModel => entry !== undefined);
    syncNetworkObservationPresentation(contentElement, hardwareSnapshot, orderedRows);
    syncNetworkSummary(host, rows);
    host.flushDOMUpdates();
};
