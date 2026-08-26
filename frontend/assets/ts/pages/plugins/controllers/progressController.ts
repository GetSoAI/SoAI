/* SoAI - Plugins page progress controller [frontend/assets/ts/pages/plugins/controllers/progressController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { StatusManager } from '@core/state/statusmanager/service.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { startPluginsModalLedUpdates, stopPluginsModalLedUpdates, type PluginsModalLedUpdateHost } from '@features/plugins/public.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';

interface PluginsProgressControllerDependencies extends PageDomOwnerHost, PageResourcesOwnerHost {
    progressMetadata: Map<string, Record<string, JsonValue>>;
    modals: ModalPresenterApi;
    getPluginStatus(plugin: PluginRecord): string;
    getBackendStatus(plugin: PluginRecord): string;
    getBackendVersion(plugin: PluginRecord): string;
    getStatusManager(): StatusManager;
    getCurrentManagingPlugin(): PluginRecord | null;
}

class PluginsProgressController {
    readonly #dependencies: PluginsProgressControllerDependencies;
    #modalLedTimerId: number | null = null;

    constructor(dependencies: PluginsProgressControllerDependencies) {
        this.#dependencies = dependencies;
    }

    #buildModalLedDependencies(): PluginsModalLedUpdateHost {
        return {
            modals: this.#dependencies.modals,
            optionalHTMLElement: (selector: string, context?: Element): HTMLElement | null => this.#dependencies.pageDom.optionalHTMLElement(selector, context),
            updateText: (target: Element | string, text: string): void => this.#dependencies.pageDom.updateText(target, text),
            getPluginStatus: (plugin: PluginRecord): string => this.#dependencies.getPluginStatus(plugin),
            getBackendStatus: (plugin: PluginRecord): string => this.#dependencies.getBackendStatus(plugin),
            getBackendVersion: (plugin: PluginRecord): string => this.#dependencies.getBackendVersion(plugin),
            statusManager: this.#dependencies.getStatusManager(),
            currentManagingPlugin: this.#dependencies.getCurrentManagingPlugin(),
            setInterval: (callback: () => void, delay: number): number | null => this.#dependencies.pageResources.setInterval(callback, delay),
            clearTimer: (timerId: number): void => this.#dependencies.pageResources.clearTimer(timerId)
        };
    }

    subscribeModalLedUpdates(): void {
        if (this.#modalLedTimerId !== null) return;
        this.#modalLedTimerId = startPluginsModalLedUpdates(this.#buildModalLedDependencies());
    }

    unsubscribeModalLedUpdates(): void {
        this.#modalLedTimerId = stopPluginsModalLedUpdates(this.#buildModalLedDependencies(), this.#modalLedTimerId);
    }

    setPluginProgressMeta(key: string, meta: Record<string, JsonValue> = {}): void {
        if (key) this.#dependencies.progressMetadata.set(key, { ...meta });
    }

    consumePluginProgressMeta(key: string): Record<string, JsonValue> | null {
        if (!key) return null;
        const meta = this.#dependencies.progressMetadata.get(key) || null;
        this.#dependencies.progressMetadata.delete(key);
        return meta;
    }

    dispose(): void {
        this.unsubscribeModalLedUpdates();
    }
}

export { PluginsProgressController };
export type { PluginsProgressControllerDependencies };
