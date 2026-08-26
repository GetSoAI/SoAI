/* SoAI - Hardware page network card renderer [frontend/assets/ts/pages/hardware/rendering/cards/NetworkCardRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildFragment } from '@core/dom/renderCache.ts';
import { i18n } from '@core/i18n/index.ts';
import { buildNetworkInterfaceModels, buildNetworkSummaryText, createNetworkInterfaceRow, DEFAULT_IGNORED_NETWORK_PREFIXES, type NetworkCardLabelSet } from '@features/hardware/public.ts';
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
                host.updateText(summary, summaryText);
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
            host.renderCachedContent(container, 'network-empty', () => {
                const emptyElement = host.createElement('div', {
                    className: 'hardware-network-empty u-text-muted'
                });
                host.updateText(emptyElement, i18n.t('hardware.cards.network.empty'));
                return emptyElement;
            });
            const summaryText = i18n.t('hardware.cards.network.summary.none');
            if (summaryText !== this.summaryText) {
                host.updateText(summary, summaryText);
                this.summaryText = summaryText;
            }
            return;
        }
        const labels = getNetworkLabels();
        const cacheKey = rows.map((networkInterface) => [networkInterface.deviceId, networkInterface.name, networkInterface.dlMbps, networkInterface.ulMbps, networkInterface.primaryAddr?.address, networkInterface.primaryAddr?.netmask, networkInterface.secondaryAddr?.address, networkInterface.mac].join('|')).join(';');
        host.renderCachedContent(container, `network::${cacheKey}`, () =>
            buildFragment(
                rows.map((row, index) => {
                    return createNetworkInterfaceRow({ host, entry: row, index: index, labels });
                })
            )
        );
        const summaryText = buildNetworkSummaryText(rows);
        if (summaryText !== this.summaryText) {
            host.updateText(summary, summaryText);
            this.summaryText = summaryText;
        }
    }
}

export { NetworkCardRenderer };
export type { NetworkCardRendererHost };
