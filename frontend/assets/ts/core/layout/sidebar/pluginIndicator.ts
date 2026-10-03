/* SoAI - Shared layout plugin indicator [frontend/assets/ts/core/layout/sidebar/pluginIndicator.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFirstRunModalPending, normalizeFirstRunModalStateMap } from '@core/firstrun/state.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';
import { syncSidebarLinkIndicator } from '@core/layout/sidebar/linkIndicator.ts';

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
        syncSidebarLinkIndicator(this.#host.getPluginsLink(), 'sidebar-plugin-indicator', this.#visible);
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
