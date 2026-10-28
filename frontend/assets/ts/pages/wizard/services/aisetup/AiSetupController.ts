/* SoAI - Wizard AI setup state, data, and subsystem ownership [frontend/assets/ts/pages/wizard/services/aisetup/AiSetupController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { LifecycleScope } from '@core/lifecycle/lifecycleScope.ts';
import { readDecodedModelCollection } from '@core/models/decodedModelCollection.ts';
import { MODELS } from '@core/realtime/streammanager/resources/ids.ts';
import type { PageStreamingContract } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { AiSetupModel, AiSetupState } from '@core/storage/aisetup/aiSetupTypes.ts';
import type { AiSetupStateUpdate } from '@core/storage/service/aiSetupActions.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { requireCatalogStore } from '@features/catalog/public.ts';
import { resolveRepositoryLinkData } from '@features/models/public.ts';
import { AiSetupCloudConnectionSession, readProviderPluginAvailability } from '@pages/wizard/services/aisetup/AiSetupCloudConnectionSession.ts';
import { isAiSetupDiscoveryReady, loadAiSetupFacts, loadEngineCandidate, resolveItemEngine, withEngineCandidate, type AiSetupFacts } from '@pages/wizard/services/aisetup/facts/service.ts';
import { deriveAiSetupProgress, isLocalDownloadComplete, type AiSetupProgressSummary } from '@pages/wizard/services/aisetup/progress/mappers.ts';
import { AiSetupModelSearchController } from '@pages/wizard/services/aisetup/AiSetupModelSearchController.ts';
import { AiSetupOperationsManager } from '@pages/wizard/services/aisetup/AiSetupOperationsManager.ts';
import { AiSetupReadinessManager } from '@pages/wizard/services/aisetup/AiSetupReadinessManager.ts';
import { createAiSetupState } from '@pages/wizard/services/aisetup/state.ts';
import type { AiSetupSnapshot } from '@pages/wizard/services/aisetup/mappers.ts';
import { findModelCatalogEntry } from '@pages/wizard/services/aisetup/catalog/constants.ts';
import { resolveStarterContextTokens } from '@pages/wizard/services/aisetup/recommendations/service.ts';

interface AiSetupStorage {
    getAiSetup(): AiSetupState | null;
    updateAiSetup(update: AiSetupStateUpdate): AiSetupState | null;
}

interface AiSetupControllerHost {
    streaming: PageStreamingContract;
    storage: AiSetupStorage;
    onChange(): void;
    notify(message: string, type: NotificationType): void;
}

class AiSetupController {
    readonly #host: AiSetupControllerHost;
    readonly operations: AiSetupOperationsManager;
    readonly readiness: AiSetupReadinessManager;
    readonly cloud: AiSetupCloudConnectionSession;
    readonly search: AiSetupModelSearchController;
    readonly #lifecycle = new LifecycleScope();
    readonly #lifecycleRun = this.#lifecycle.begin();
    readonly #engineRefreshSequences = new Map<string, SequenceToken>();
    readonly #factsLoadSequence = new SequenceToken();
    #facts: AiSetupFacts | null = null;
    #factsLoad: Promise<AiSetupFacts> | null = null;
    #models: readonly ModelData[] = [];
    #unsubscribeModels: (() => void) | null = null;
    searchOpen = false;
    cloudFilter = '';

    constructor(host: AiSetupControllerHost) {
        this.#host = host;
        const onChange = (): void => this.#notifyChange();
        this.operations = new AiSetupOperationsManager({
            streaming: host.streaming,
            getSetup: () => this.requireSetup(),
            updateSetup: (update) => this.updateSetup(update),
            getFacts: () => this.#facts,
            getModels: () => this.#models,
            onEngineInstalled: (pluginName) => this.#reloadEngine(pluginName),
            onChange,
            notify: (message, type) => host.notify(message, type)
        });
        this.readiness = new AiSetupReadinessManager({
            getSetup: () => this.requireSetup(),
            updateSetup: (update) => this.updateSetup(update),
            getModels: () => this.#models,
            resolveStarterContextTokens: (item) => this.#resolveStarterContext(item),
            refreshModels: () => this.refreshModels(),
            onChange
        });
        this.cloud = new AiSetupCloudConnectionSession({
            updateSetup: (update) => this.updateSetup(update),
            refreshModels: async () => {
                await this.refreshModels();
            },
            onChange
        });
        this.search = new AiSetupModelSearchController(onChange);
    }

    get facts(): AiSetupFacts | null {
        return this.#facts;
    }

    get models(): readonly ModelData[] {
        return this.#models;
    }

    get setup(): AiSetupState | null {
        return this.#host.storage.getAiSetup();
    }

    readonly requireSetup = (): AiSetupState => {
        const setup = this.#host.storage.getAiSetup();
        if (setup === null) throw new Error('AI setup state is unavailable');
        return setup;
    };

    ensureSetup(): AiSetupState {
        const existing = this.setup;
        if (existing !== null) return existing;
        const created = this.#host.storage.updateAiSetup(() => createAiSetupState());
        if (created === null) throw new Error('AI setup state could not be created');
        return created;
    }

    readonly updateSetup = (update: (setup: AiSetupState) => AiSetupState): AiSetupState => {
        const next = this.#host.storage.updateAiSetup((current) => {
            if (current === null) throw new Error('AI setup state is unavailable');
            return update(current);
        });
        if (next === null) throw new Error('AI setup state update produced no state');
        return next;
    };

    async activate(): Promise<AiSetupFacts> {
        const signal = this.#lifecycleRun.signal;
        throwIfAborted(signal);
        if (this.#unsubscribeModels === null) {
            this.#unsubscribeModels = this.#host.streaming.subscribeResourceValue(MODELS, (value) => this.#applyModels(value));
            void this.#host.streaming.ensureSubscriptions({ signal }).catch((error) => {
                if (!signal.aborted) errorHandler.warn('WizardAiSetup', 'Model catalog subscription failed', ensureError(error));
            });
        }
        if (this.#factsLoad === null) {
            const sequence = this.#factsLoadSequence.next();
            for (const refreshSequence of this.#engineRefreshSequences.values()) refreshSequence.invalidate();
            this.#factsLoad = loadAiSetupFacts(signal).then((facts) => {
                throwIfAborted(signal);
                if (this.#factsLoadSequence.isActive(sequence)) this.#facts = facts;
                else this.#factsLoad = null;
                return facts;
            });
        }
        const loading = this.#factsLoad;
        try {
            await loading;
        } catch (error) {
            if (this.#factsLoad === loading) this.#factsLoad = null;
            throw ensureError(error);
        }
        throwIfAborted(signal);
        const facts = this.requireFacts();
        if (!isAiSetupDiscoveryReady(facts) && this.#factsLoad === loading) this.#factsLoad = null;
        if (this.setup !== null) {
            this.operations.reconcile();
            if (isAiSetupDiscoveryReady(facts)) this.readiness.schedule();
        }
        return facts;
    }

    requireFacts(): AiSetupFacts {
        if (this.#facts === null) throw new Error('AI setup facts are not loaded');
        return this.#facts;
    }

    needsConnectStep(): boolean {
        const setup = this.setup;
        if (setup === null || this.#facts === null) return true;
        if (setup.sources.cloud) return true;
        return setup.sources.local && (setup.engine.mode === 'manual' || this.#facts.automatic.status !== 'installed');
    }

    progress(): AiSetupProgressSummary {
        return deriveAiSetupProgress({ setup: this.requireSetup(), facts: this.#facts, models: this.#models, observations: this.operations.observations, readiness: this.readiness.phases, stalledDiscovery: this.operations.stalledDiscovery });
    }

    snapshot(): AiSetupSnapshot {
        return {
            setup: this.requireSetup(),
            facts: this.requireFacts(),
            models: this.#models,
            progress: this.progress(),
            connection: this.cloud.state,
            providerAvailability: readProviderPluginAvailability(),
            search: this.search.state,
            localDownloadComplete: isLocalDownloadComplete(this.requireSetup(), this.operations.observations),
            searchOpen: this.searchOpen,
            cloudFilter: this.cloudFilter,
            resolveRepositoryUrl: (pluginName, repository) => resolveRepositoryLinkData(requireCatalogStore().getPlugin(pluginName), repository)?.url ?? null
        };
    }

    readonly refreshModels = async (): Promise<readonly ModelData[]> => {
        const payload = await this.#host.streaming.runtime().resources.refresh(MODELS, { allowDiscovery: true, throwOnError: true });
        this.#applyModels(payload ?? null);
        return this.#models;
    };

    destroy(): void {
        this.#lifecycle.abort();
        this.#unsubscribeModels?.();
        this.#unsubscribeModels = null;
        this.operations.dispose();
        this.readiness.dispose();
        this.cloud.dispose();
        this.search.dispose();
    }

    #applyModels(value: JsonValue | null): void {
        const models = value === null ? null : readDecodedModelCollection(value);
        if (models === null || !this.#lifecycle.isCurrent(this.#lifecycleRun)) return;
        this.#models = models;
        if (this.setup !== null) {
            this.operations.reconcile();
            if (this.#facts !== null && isAiSetupDiscoveryReady(this.#facts)) this.readiness.schedule();
        }
        this.#notifyChange();
    }

    async #reloadEngine(pluginName: string): Promise<void> {
        let sequence = this.#engineRefreshSequences.get(pluginName);
        if (sequence === undefined) {
            sequence = new SequenceToken();
            this.#engineRefreshSequences.set(pluginName, sequence);
        }
        await this.activate();
        const token = sequence.next();
        this.#factsLoadSequence.invalidate();
        const refreshed = await loadEngineCandidate(pluginName, this.#lifecycleRun.signal);
        if (this.#facts !== null && this.#lifecycle.isCurrent(this.#lifecycleRun) && sequence.isActive(token)) {
            this.#facts = withEngineCandidate(this.#facts, refreshed);
            if (!isAiSetupDiscoveryReady(this.#facts)) this.#factsLoad = null;
        }
    }

    #resolveStarterContext(item: AiSetupModel): number | null {
        const entry = findModelCatalogEntry(item.catalogId);
        if (entry === null || this.#facts === null) return null;
        return resolveStarterContextTokens(entry, this.#facts.hardware, resolveItemEngine(this.#facts, item.pluginName));
    }

    #notifyChange(): void {
        if (this.#lifecycle.isCurrent(this.#lifecycleRun)) this.#host.onChange();
    }
}

export { AiSetupController };
export type { AiSetupControllerHost, AiSetupStorage };
