/* SoAI - Plugins page DOM contracts [frontend/assets/ts/pages/plugins/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isHTMLElement } from '@core/typeGuards.ts';

interface PluginsPageDomHost {
    getDomContext: () => Element | null;
}

type PluginsUi = {
    root: HTMLElement;
    grid: HTMLElement;
    listBody: HTMLElement;
    viewModeToggleButton: HTMLButtonElement;
};

export const optionalPluginsRoot = (host: PluginsPageDomHost): HTMLElement | null => {
    const root = host.getDomContext();
    if (!isHTMLElement(root)) {
        return null;
    }
    if (root.dataset['section'] === 'plugins') {
        return root;
    }
    const section = dom.resolve('[data-section="plugins"]', root);
    return isHTMLElement(section) ? section : null;
};

export const requirePluginsRoot = (host: PluginsPageDomHost): HTMLElement => {
    const root = optionalPluginsRoot(host);
    if (!root) {
        throw new Error('Plugins page requires a host container');
    }
    return root;
};

const requirePluginsUi = (host: PluginsPageDomHost): PluginsUi => {
    const root = requirePluginsRoot(host);
    const grid = dom.resolve('#plugins-grid', root);
    const listBody = dom.resolve('#plugins-list-body', root);
    const viewModeToggleButton = dom.resolve('#plugins-view-mode-toggle', root);
    if (!(grid instanceof HTMLElement) || !(listBody instanceof HTMLElement) || !(viewModeToggleButton instanceof HTMLButtonElement)) {
        throw new Error('Plugins page requires collection view mode surfaces');
    }
    return { root, grid, listBody, viewModeToggleButton };
};

export { requirePluginsUi };
export type { PluginsUi, PluginsPageDomHost };
