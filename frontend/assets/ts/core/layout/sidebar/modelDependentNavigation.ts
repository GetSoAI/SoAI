/* SoAI - Shared layout model dependent navigation [frontend/assets/ts/core/layout/sidebar/modelDependentNavigation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { hasChatSelectableModels } from '@core/models/chatModelAvailability.ts';
import { readDecodedModelCollection } from '@core/models/decodedModelCollection.ts';
import { getStreamRuntime } from '@core/realtime/streammanager/public.ts';
import type { StreamSubscriptions } from '@core/realtime/streammanager/streamSubscriptions.ts';
import { MODELS } from '@core/realtime/streammanager/resources/ids.ts';
import type { ResourceSnapshot } from '@core/realtime/streammanager/types.ts';
import { resolveOptionalKernelService } from '@core/runtime/runtimeContext.ts';
import { isKeyValueStorageContract } from '@core/storage/guards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { SidebarConfigEntry } from '@core/layout/sidebar/view.ts';

type ModelDependentNavigationSnapshotState = 'unknown' | 'empty' | 'hasSelectable';

type SidebarModelDependentNavigationHost = {
    refreshSidebar: (options?: { syncRoute?: boolean }) => Promise<void>;
};

const MODEL_DEPENDENT_UNLOCK_KEY = 'model_dependent_pages_unlocked';
const MODEL_DEPENDENT_PAGE_IDS: readonly string[] = ['chat', 'automation'];

class SidebarModelDependentNavigationGate {
    readonly #host: SidebarModelDependentNavigationHost;
    #snapshotState: ModelDependentNavigationSnapshotState = 'unknown';
    #unlocked: boolean = false;
    #refreshArmed: boolean = false;
    #unsubscribe: (() => void) | null = null;
    #lifecycleGeneration: number = 0;

    constructor(host: SidebarModelDependentNavigationHost) {
        this.#host = host;
    }

    async initialize(): Promise<void> {
        this.dispose();
        const generation = ++this.#lifecycleGeneration;
        this.#unlocked = this.#readUnlocked();
        const runtime = getStreamRuntime();
        const payload = await runtime.resources.ensureResourceStarted(MODELS, { allowDiscovery: true, throwOnError: false });
        if (generation !== this.#lifecycleGeneration) {
            return;
        }
        this.#applyPayload(payload);
        this.#unsubscribe = this.#subscribe(runtime.subscriptions);
        this.#refreshArmed = true;
    }

    dispose(): void {
        this.#lifecycleGeneration += 1;
        this.#refreshArmed = false;
        this.#unsubscribe?.();
        this.#unsubscribe = null;
        this.#snapshotState = 'unknown';
    }

    filterEntries(entries: SidebarConfigEntry[]): SidebarConfigEntry[] {
        if (!this.#shouldHideModelDependentPages()) {
            return entries;
        }
        return entries.filter((entry) => !entry.id || !MODEL_DEPENDENT_PAGE_IDS.includes(entry.id));
    }

    #subscribe(subscriptions: StreamSubscriptions): () => void {
        return subscriptions.subscribeResourceState(
            MODELS,
            (snapshot) => {
                this.#applySnapshot(snapshot);
            },
            { immediate: true, ensureStart: false }
        );
    }

    #applySnapshot(snapshot: ResourceSnapshot): void {
        if (snapshot.status === 'ready' && snapshot.value !== null) {
            this.#applyPayload(snapshot.value);
            return;
        }
        if (snapshot.status === 'error') {
            this.#setSnapshotState('unknown');
        }
    }

    #applyPayload(payload: JsonValue | null): void {
        if (payload === null) {
            this.#setSnapshotState('unknown');
            return;
        }
        const models = readDecodedModelCollection(payload);
        if (models === null) {
            this.#setSnapshotState('unknown');
            return;
        }
        if (hasChatSelectableModels(models)) {
            this.#setSelectableSnapshotState();
            return;
        }
        this.#setSnapshotState('empty');
    }

    #setSelectableSnapshotState(): void {
        const wasHidden = this.#shouldHideModelDependentPages();
        this.#persistUnlocked();
        this.#snapshotState = 'hasSelectable';
        const isHidden = this.#shouldHideModelDependentPages();
        if (wasHidden !== isHidden) {
            this.#refreshSidebar();
        }
    }

    #setSnapshotState(state: ModelDependentNavigationSnapshotState): void {
        const wasHidden = this.#shouldHideModelDependentPages();
        this.#snapshotState = state;
        const isHidden = this.#shouldHideModelDependentPages();
        if (wasHidden !== isHidden) {
            this.#refreshSidebar();
        }
    }

    #shouldHideModelDependentPages(): boolean {
        return !this.#unlocked && this.#snapshotState === 'empty';
    }

    #readUnlocked(): boolean {
        const storage = resolveModelDependentNavigationStorage();
        return storage?.get(MODEL_DEPENDENT_UNLOCK_KEY, false) === true;
    }

    #persistUnlocked(): void {
        if (this.#unlocked) {
            return;
        }
        this.#unlocked = true;
        const storage = resolveModelDependentNavigationStorage();
        if (!storage) {
            errorHandler.warn('Sidebar', 'Storage service unavailable for model navigation unlock state');
            return;
        }
        try {
            storage.set(MODEL_DEPENDENT_UNLOCK_KEY, true);
        } catch (error) {
            errorHandler.warn('Sidebar', 'Failed to persist model navigation unlock state', ensureError(error));
        }
    }

    #refreshSidebar(): void {
        if (!this.#refreshArmed) {
            return;
        }
        this.#host.refreshSidebar({ syncRoute: true }).catch((error) => {
            errorHandler.warn('Sidebar', 'Model dependent navigation refresh failed', ensureError(error));
        });
    }
}

const resolveModelDependentNavigationStorage = () => {
    const storage = resolveOptionalKernelService('core.storage');
    return isKeyValueStorageContract(storage) ? storage : null;
};

export { SidebarModelDependentNavigationGate };
