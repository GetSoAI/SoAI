/* SoAI - Shared layout plugin indicator [frontend/assets/ts/core/layout/sidebar/pluginIndicator.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFirstRunModalPending, normalizeFirstRunModalStateMap } from '@core/firstrun/state.ts';
import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';
import { ARIA_HIDDEN_ATTR, resolveHTMLElement } from '@core/layout/sidebar/dom.ts';

interface SidebarStoragePluginIndicatorContract {
    get?: ((key: string, defaultValue?: JsonValue) => JsonValue) | undefined;
}

interface SidebarPluginIndicatorHost {
    getPluginsLink: () => HTMLElement | null;
    resolveStorage: () => Promise<SidebarStoragePluginIndicatorContract | null>;
}

class SidebarPluginIndicatorController {
    readonly #host: SidebarPluginIndicatorHost;
    #visible: boolean = false;

    constructor(host: SidebarPluginIndicatorHost) {
        this.#host = host;
    }

    updateIndicator(): void {
        const link = this.#host.getPluginsLink();
        const existing = link ? resolveHTMLElement('.sidebar-plugin-indicator', link) : null;
        if (!this.#visible) {
            if (existing) dom.remove(existing);
            return;
        }
        if (!link) return;
        const iconButton = resolveHTMLElement('.sidebar-icon-button', link);
        const target = iconButton ?? link;
        if (existing) {
            if (existing.parentElement !== target) {
                dom.appendChild(target, existing);
            }
            existing.removeAttribute('hidden');
            return;
        }
        const indicator = dom.create('span', { className: 'sidebar-plugin-indicator', [ARIA_HIDDEN_ATTR]: 'true' });
        dom.appendChild(target, indicator);
    }

    async refreshFromStorage(): Promise<void> {
        const storage = await this.#host.resolveStorage();
        let pending = false;
        if (storage) {
            if (!isFunction(storage.get)) {
                errorHandler.warn('Sidebar', 'Storage service missing get(key)');
                pending = false;
            } else {
                pending = isFirstRunModalPending(normalizeFirstRunModalStateMap(storage.get('soai_first_run_modals', {})), 'pluginsIntro');
            }
        }
        this.setVisible(pending);
    }

    setVisible(visible: boolean): void {
        if (this.#visible === visible) return;
        this.#visible = visible;
        this.updateIndicator();
    }
}

const isSidebarStoragePluginIndicatorContract = <T>(value: T): value is T & SidebarStoragePluginIndicatorContract => {
    if (!isObject(value)) return false;
    if ('get' in value && !isFunction(value.get)) {
        return false;
    }
    return true;
};

export { SidebarPluginIndicatorController, isSidebarStoragePluginIndicatorContract };
export type { SidebarPluginIndicatorHost, SidebarStoragePluginIndicatorContract };
