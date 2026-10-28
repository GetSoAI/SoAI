/* SoAI - Hardware page network card renderer [frontend/assets/ts/pages/hardware/rendering/cards/NetworkCardRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { reconcileHardwareRows } from '@pages/hardware/rendering/cards/effects.ts';
import { i18n } from '@core/i18n/index.ts';
import { buildNetworkEmptyText, buildNetworkInterfaceModels, buildNetworkSummaryText, syncNetworkSummaryPresentation, createNetworkInterfaceRow, syncNetworkObservationPresentation, DEFAULT_IGNORED_NETWORK_PREFIXES, getWindowsNetworkInventoryStatus, type NetworkCardLabelSet } from '@features/hardware/public.ts';
import { BaseHardwareCardRenderer, type BaseHardwareCardRendererHost } from '@pages/hardware/rendering/cards/BaseHardwareCardRenderer.ts';
import type { HardwarePageSnapshot } from '@pages/hardware/types.ts';

interface NetworkCardRendererHost extends BaseHardwareCardRendererHost {
    optionalUI(selector: string): Element | null;
    renderCachedContent(container: Element, key: string, factory: () => Element | DocumentFragment): void;
}

interface NetworkRendererOptions {
    host: NetworkCardRendererHost;
}

const getNetworkLabels = (): NetworkCardLabelSet => ({
    ipv4: i18n.t('hardware.cards.network.labels.ipv4'),
    ipv6: i18n.t('hardware.cards.network.labels.ipv6'),
    mac: i18n.t('hardware.cards.network.labels.mac'),
    download: i18n.t('hardware.cards.network.labels.download'),
    upload: i18n.t('hardware.cards.network.labels.upload')
});

class NetworkCardRenderer extends BaseHardwareCardRenderer<NetworkCardRendererHost> {
    constructor({ host }: NetworkRendererOptions) {
        super({ host, type: 'network' });
    }

    override render(snapshot: HardwarePageSnapshot | null): void {
        const { host } = this;
        const container = host.optionalUI('hardwareNetworkContent');
        const summary = host.optionalUI('hardwareNetworkSummary');
        if (!container || !summary) {
            if (!summary) this.summaryText = null;
            return;
        }
        if (!snapshot) {
            host.renderCachedContent(container, 'network-empty', () => {
                const emptyElement = host.createElement('div', {
                    className: 'hardware-network-empty u-text-muted'
                });
                host.updateText(emptyElement, i18n.t('hardware.cards.network.empty'));
                return emptyElement;
            });
            const summaryText = i18n.t('hardware.cards.network.summary.none');
            if (summaryText !== this.summaryText) {
                syncNetworkSummaryPresentation(summary, []);
                this.summaryText = summaryText;
            }
            return;
        }

        const speedsRaw = snapshot.networkSpeed ?? {};

        const rows = buildNetworkInterfaceModels(snapshot, {
            speeds: speedsRaw,
            ignorePrefixes: DEFAULT_IGNORED_NETWORK_PREFIXES
        });
        if (!rows.length) {
            const windowsInventoryStatus = getWindowsNetworkInventoryStatus(snapshot);
            host.renderCachedContent(container, windowsInventoryStatus === 'unavailable' ? 'network-unavailable' : 'network-empty', () => {
                const emptyElement = host.createElement('div', {
                    className: 'hardware-network-empty u-text-muted'
                });
                host.updateText(emptyElement, buildNetworkEmptyText(windowsInventoryStatus));
                return emptyElement;
            });
            const summaryText = buildNetworkSummaryText(rows, windowsInventoryStatus);
            if (summaryText !== this.summaryText) {
                syncNetworkSummaryPresentation(summary, [], windowsInventoryStatus);
                this.summaryText = summaryText;
            }
            return;
        }
        const labels = getNetworkLabels();
        reconcileHardwareRows(
            container,
            '.hardware-network-row',
            rows,
            (row) => row.deviceId,
            (row, index) => createNetworkInterfaceRow({ host, entry: row, index, labels })
        );
        syncNetworkObservationPresentation(container, snapshot, rows);
        const summaryText = buildNetworkSummaryText(rows);
        if (summaryText !== this.summaryText) {
            syncNetworkSummaryPresentation(summary, rows);
            this.summaryText = summaryText;
        }
    }
}

export { NetworkCardRenderer };
export type { NetworkCardRendererHost };
