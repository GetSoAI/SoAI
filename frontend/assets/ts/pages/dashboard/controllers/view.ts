/* SoAI - Dashboard page controllers rendering [frontend/assets/ts/pages/dashboard/controllers/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { narrowHTMLElement } from '@core/dom/narrowElement.ts';
import { i18n } from '@core/i18n/index.ts';
import { buildStorageSummaryText, buildVolumeModels, createStorageInterfaceRow, syncStorageObservationPresentation, isStorageUnavailable, isHardwareSnapshot, type StorageCardLabelSet, type VolumeModel } from '@features/hardware/public.ts';
import type { DashboardHardwareSectionsRenderContext } from '@pages/dashboard/controllers/contracts.ts';
import { syncKeyedList, type KeyedListRow } from '@pages/dashboard/controllers/effects.ts';

const getStorageLabels = (): StorageCardLabelSet => ({
    mount: i18n.t('hardware.cards.storage.labels.mount'),
    type: i18n.t('hardware.cards.storage.labels.type'),
    used: i18n.t('hardware.cards.storage.labels.used'),
    available: i18n.t('hardware.cards.storage.labels.available'),
    total: i18n.t('hardware.cards.storage.labels.total')
});

const syncStorageSummary = (host: DashboardHardwareSectionsRenderContext['host'], volumes: readonly VolumeModel[]): void => {
    const summary = host.optionalHTMLElement('#dashboardStorageSummary');
    if (summary) {
        summary.textContent = buildStorageSummaryText(volumes);
    }
};

export const renderStorageSection = ({ host, state, isDestroyed }: DashboardHardwareSectionsRenderContext): void => {
    if (isDestroyed()) {
        return;
    }

    const content = host.requireUI('storage-content');
    const contentElement = narrowHTMLElement(content, 'storage content');

    if (!state.hasHardware()) {
        const loadingNode = host.createElement('div', { className: 'hardware-storage-placeholder u-text-muted' }, i18n.t('hardware.cards.storage.waiting'));
        host.replaceElementContent(contentElement, narrowHTMLElement(loadingNode, 'storage loading node'), { escape: false });
        syncStorageSummary(host, []);
        host.flushDOMUpdates();
        return;
    }

    const snapshot = state.getRawHardwareSnapshot();
    const volumes = buildVolumeModels(isHardwareSnapshot(snapshot) ? snapshot : undefined);
    if (!volumes.length) {
        const unavailable = isStorageUnavailable(isHardwareSnapshot(snapshot) ? snapshot : undefined);
        const emptyNode = host.createElement('div', { className: 'hardware-storage-empty u-text-muted' }, unavailable ? i18n.t('hardware.cards.storage.unavailable') : i18n.t('hardware.cards.storage.empty'));
        host.replaceElementContent(contentElement, narrowHTMLElement(emptyNode, 'storage empty node'), { escape: false });
        const summary = host.optionalHTMLElement('#dashboardStorageSummary');
        if (unavailable && summary) summary.textContent = i18n.t('hardware.cards.storage.unavailable');
        else syncStorageSummary(host, []);
        host.flushDOMUpdates();
        return;
    }

    const keyedRows: KeyedListRow<VolumeModel>[] = volumes.map((volume) => ({
        key: `${volume.deviceId}|${volume.mount}`,
        signature: [volume.filesystem, volume.mount, volume.fstype, volume.percentUsed.toFixed(3), volume.used, volume.available, volume.size, JSON.stringify(volume.observationStatus)].join('|'),
        value: volume
    }));
    const labels = getStorageLabels();
    syncKeyedList({
        content: contentElement,
        listClassName: 'hardware-storage-list',
        rows: keyedRows,
        createList: () => narrowHTMLElement(host.createElement('div', { className: 'hardware-storage-list' }), 'storage volume list'),
        createRow: (volume, index) => createStorageInterfaceRow({ host, volume, index, labels })
    });
    const orderedVolumes = dom
        .resolveAll('.hardware-storage-row', contentElement)
        .map((row) => volumes.find((volume) => `${volume.deviceId}|${volume.mount}` === (row instanceof HTMLElement ? row.dataset['dashboardRowKey'] : null)))
        .filter((volume): volume is VolumeModel => volume !== undefined);
    syncStorageObservationPresentation(contentElement, isHardwareSnapshot(snapshot) ? snapshot : undefined, orderedVolumes);
    syncStorageSummary(host, volumes);
    host.flushDOMUpdates();
};
