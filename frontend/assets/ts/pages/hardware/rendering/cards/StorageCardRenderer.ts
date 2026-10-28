/* SoAI - Hardware page storage card renderer [frontend/assets/ts/pages/hardware/rendering/cards/StorageCardRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { reconcileHardwareRows } from '@pages/hardware/rendering/cards/effects.ts';
import { i18n } from '@core/i18n/index.ts';
import { buildStorageSummaryText, buildVolumeModels, createStorageInterfaceRow, syncStorageObservationPresentation, isStorageUnavailable, type StorageCardLabelSet } from '@features/hardware/public.ts';
import { BaseHardwareCardRenderer, type BaseHardwareCardRendererHost } from '@pages/hardware/rendering/cards/BaseHardwareCardRenderer.ts';
import type { HardwarePageSnapshot } from '@pages/hardware/types.ts';

interface StorageCardRendererHost extends BaseHardwareCardRendererHost {
    optionalUI(selector: string): Element | null;
    renderCachedContent(container: Element, key: string, factory: () => Element | DocumentFragment): void;
}

interface StorageRendererOptions {
    host: StorageCardRendererHost;
}

const getStorageLabels = (): StorageCardLabelSet => ({
    mount: i18n.t('hardware.cards.storage.labels.mount'),
    type: i18n.t('hardware.cards.storage.labels.type'),
    used: i18n.t('hardware.cards.storage.labels.used'),
    available: i18n.t('hardware.cards.storage.labels.available'),
    total: i18n.t('hardware.cards.storage.labels.total')
});

class StorageCardRenderer extends BaseHardwareCardRenderer<StorageCardRendererHost> {
    constructor({ host }: StorageRendererOptions) {
        super({ host, type: 'storage' });
    }

    override render(snapshot: HardwarePageSnapshot | null): void {
        const { host } = this;
        const container = host.optionalUI('hardwareStorageContent');
        const summary = host.optionalUI('hardwareStorageSummary');
        if (!container || !summary) {
            if (!summary) this.summaryText = null;
            return;
        }
        const rows = buildVolumeModels(snapshot);
        if (!rows.length) {
            const unavailable = isStorageUnavailable(snapshot);
            host.renderCachedContent(container, unavailable ? 'storage-unavailable' : 'storage-empty', () => {
                const emptyElement = host.createElement('div', {
                    className: 'hardware-storage-empty u-text-muted'
                });
                host.updateText(emptyElement, unavailable ? i18n.t('hardware.cards.storage.unavailable') : i18n.t('hardware.cards.storage.empty'));
                return emptyElement;
            });
            const summaryText = unavailable ? i18n.t('hardware.cards.storage.unavailable') : i18n.t('hardware.cards.storage.summary.none');
            if (summaryText !== this.summaryText) {
                host.updateText(summary, summaryText);
                this.summaryText = summaryText;
            }
            return;
        }
        const labels = getStorageLabels();
        reconcileHardwareRows(
            container,
            '.hardware-storage-row',
            rows,
            (row) => `${row.deviceId}|${row.mount}`,
            (row, index) => createStorageInterfaceRow({ host, volume: row, index, labels })
        );
        syncStorageObservationPresentation(container, snapshot, rows);
        const summaryText = buildStorageSummaryText(rows);
        if (summaryText !== this.summaryText) {
            host.updateText(summary, summaryText);
            this.summaryText = summaryText;
        }
    }
}

export { StorageCardRenderer };
export type { StorageCardRendererHost };
