/* SoAI - Plugins page progress controller [frontend/assets/ts/pages/plugins/controllers/progressController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { StatusManager } from '@core/state/statusmanager/service.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { AnimationFrameRenderQueue } from '@core/animations/renderQueue.ts';
import { matches } from '@core/dom/dom.ts';
import { runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';
import { normalizeProgress } from '@core/primitives/progress.ts';
import { startPluginsModalLedUpdates, stopPluginsModalLedUpdates, type PluginsModalLedUpdateHost } from '@features/plugins/public.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import { requireTaskOperationsApi } from '@core/tasks/serviceAccess.ts';
import type { TaskOperationEntry, TaskOperationsApi } from '@core/tasks/protocols.ts';
import { PLUGIN_CARD_SELECTOR } from '@pages/plugins/controllers/pluginsPageRuntimeSupport.ts';
import { optionalPluginsRoot } from '@pages/plugins/dom.ts';
import { PluginOperationProgressPresentationController, type PluginOperationProjection } from '@pages/plugins/controllers/operationProgressPresentationController.ts';

const PLUGIN_PROGRESS_OPERATION_TYPES: readonly string[] = Object.freeze(['backend-install', 'backend-update', 'backend-remove', 'model-download', 'model-delete', 'plugin-clone', 'plugin-delete']);
const OPERATION_ITEM_SELECTOR = `${PLUGIN_CARD_SELECTOR}, .plugins-list-row`;

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
    readonly #taskOperations: TaskOperationsApi;
    readonly #renderQueue: AnimationFrameRenderQueue<boolean>;
    readonly #operationPresentation: PluginOperationProgressPresentationController;
    #unsubscribeOperations: (() => void) | null = null;
    #operationByPluginKey = new Map<string, PluginOperationProjection>();
    #activePluginKeys = new Set<string>();
    #modalLedTimerId: number | null = null;
    #initialized = false;
    #disposed = false;

    constructor(dependencies: PluginsProgressControllerDependencies) {
        this.#dependencies = dependencies;
        this.#taskOperations = requireTaskOperationsApi();
        this.#operationPresentation = new PluginOperationProgressPresentationController(dependencies);
        this.#renderQueue = new AnimationFrameRenderQueue<boolean>({
            label: 'PluginsProgressController',
            merge: () => true,
            render: () => this.#renderMountedItems(),
            isDisposed: () => this.#disposed,
            requestAnimationFrame: (callback) => this.#dependencies.pageResources.tracker.requestAnimationFrame(callback),
            cancelAnimationFrame: (frameId) => this.#dependencies.pageResources.tracker.cancelAnimationFrame(frameId)
        });
    }

    initializeOperationProgress(): void {
        if (this.#initialized || this.#disposed) return;
        const unsubscribe = this.#taskOperations.subscribeOperations({ types: PLUGIN_PROGRESS_OPERATION_TYPES }, (operations) => this.#consumeOperations(operations));
        this.#unsubscribeOperations = this.#dependencies.pageResources.track(unsubscribe);
        this.#initialized = true;
    }

    synchronizeCommittedItems(mountedElements: readonly HTMLElement[]): void {
        if (this.#disposed) return;
        const items = new Set<HTMLElement>();
        for (const mountedElement of mountedElements) {
            if (matches(mountedElement, OPERATION_ITEM_SELECTOR)) {
                items.add(mountedElement);
            }
            for (const candidate of this.#dependencies.pageDom.query(OPERATION_ITEM_SELECTOR, mountedElement)) {
                if (!(candidate instanceof HTMLElement)) {
                    throw new TypeError('Plugins collection operation item must be an HTMLElement');
                }
                items.add(candidate);
            }
        }
        this.#operationPresentation.apply(items, this.#operationByPluginKey, this.#activePluginKeys, (source) => this.#taskOperations.getPluginKey(source));
    }

    #consumeOperations(operations: TaskOperationEntry[]): void {
        const candidate = new Map<string, PluginOperationProjection>();
        const activePluginKeys = new Set<string>();
        const invalidPluginKeys = new Set<string>();
        for (const operation of operations) {
            const pluginKey = this.#taskOperations.getPluginKey(operation.pluginKey) ?? this.#taskOperations.getPluginKey(operation.pluginName);
            if (!pluginKey || invalidPluginKeys.has(pluginKey)) continue;
            activePluginKeys.add(pluginKey);
            if (candidate.has(pluginKey)) {
                candidate.delete(pluginKey);
                invalidPluginKeys.add(pluginKey);
                continue;
            }
            const progress = operation.progress === undefined ? 0 : normalizeProgress(operation.progress);
            if (progress === null) {
                invalidPluginKeys.add(pluginKey);
                continue;
            }
            candidate.set(pluginKey, { type: operation.type, progress });
        }
        if (this.#mapsEqual(this.#operationByPluginKey, candidate) && this.#setsEqual(this.#activePluginKeys, activePluginKeys)) return;
        this.#operationByPluginKey = candidate;
        this.#activePluginKeys = activePluginKeys;
        this.#renderQueue.schedule(true);
    }

    #mapsEqual(left: ReadonlyMap<string, PluginOperationProjection>, right: ReadonlyMap<string, PluginOperationProjection>): boolean {
        if (left.size !== right.size) return false;
        for (const [key, value] of left) {
            const next = right.get(key);
            if (!next || next.type !== value.type || next.progress !== value.progress) return false;
        }
        return true;
    }

    #setsEqual(left: ReadonlySet<string>, right: ReadonlySet<string>): boolean {
        if (left.size !== right.size) return false;
        for (const key of left) {
            if (!right.has(key)) return false;
        }
        return true;
    }

    #renderMountedItems(): void {
        const root = optionalPluginsRoot({ getDomContext: () => this.#dependencies.pageDom.getContext() });
        if (!root) return;
        const items = new Set<HTMLElement>();
        for (const item of this.#dependencies.pageDom.query(OPERATION_ITEM_SELECTOR, root)) {
            if (!(item instanceof HTMLElement)) {
                throw new TypeError('Plugins collection operation item must be an HTMLElement');
            }
            items.add(item);
        }
        this.#operationPresentation.apply(items, this.#operationByPluginKey, this.#activePluginKeys, (source) => this.#taskOperations.getPluginKey(source));
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
        if (this.#disposed) return;
        this.#disposed = true;
        const failures: Error[] = [];
        const unsubscribe = this.#unsubscribeOperations;
        this.#unsubscribeOperations = null;
        if (unsubscribe) {
            runCleanupStepCollectingFailure(() => this.#dependencies.pageResources.untrack(unsubscribe), failures);
            runCleanupStepCollectingFailure(unsubscribe, failures);
        }
        runCleanupStepCollectingFailure(() => this.#renderQueue.dispose(), failures);
        this.#operationByPluginKey.clear();
        this.#activePluginKeys.clear();
        runCleanupStepCollectingFailure(() => this.#renderMountedItems(), failures);
        runCleanupStepCollectingFailure(() => this.unsubscribeModalLedUpdates(), failures);
        throwCollectedCleanupFailures(failures);
    }
}

export { PluginsProgressController };
export type { PluginsProgressControllerDependencies };
