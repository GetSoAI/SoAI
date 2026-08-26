/* SoAI - Base hardware card renderer [frontend/assets/ts/pages/hardware/rendering/cards/BaseHardwareCardRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { HardwarePageSnapshot } from '@pages/hardware/types.ts';

interface BaseHardwareCardRendererHost {
    createElement(tagName: string, options?: { className?: string }, child?: string | Node): HTMLElement;
    updateText(element: Element, text: string): void;
}

interface BaseHardwareCardRendererOptions<THost extends BaseHardwareCardRendererHost> {
    host: THost;
    type: string;
}

class BaseHardwareCardRenderer<THost extends BaseHardwareCardRendererHost = BaseHardwareCardRendererHost> {
    summaryText: string | null = null;
    protected host: THost;
    protected type: string;

    constructor({ host, type }: BaseHardwareCardRendererOptions<THost>) {
        if (!host) {
            throw new Error(`${this.constructor.name} requires a host reference`);
        }
        if (!type) {
            throw new Error(`${this.constructor.name} requires a type parameter`);
        }
        this.host = host;
        this.type = type;
    }

    buildStatItem(label: string, value: string): HTMLElement {
        const { host, type } = this;
        const statItem = host.createElement('div', { className: `hardware-${type}-stat-item hardware-resource-stat-item` });
        const labelElement = host.createElement('span', { className: `hardware-${type}-stat-label hardware-resource-stat-label` });
        const valueElement = host.createElement('span', { className: `hardware-${type}-stat-value hardware-resource-stat-value` });
        host.updateText(labelElement, label);
        host.updateText(valueElement, value);
        statItem.append(labelElement, valueElement);
        return statItem;
    }

    render(_snapshot: HardwarePageSnapshot | null): void {
        throw new Error(`${this.constructor.name} must implement render()`);
    }
}

export { BaseHardwareCardRenderer };
export type { BaseHardwareCardRendererHost, BaseHardwareCardRendererOptions };
