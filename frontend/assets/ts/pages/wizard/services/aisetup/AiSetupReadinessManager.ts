/* SoAI - Wizard AI setup model configuration and generation tests [frontend/assets/ts/pages/wizard/services/aisetup/AiSetupReadinessManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getApiClient } from '@core/api/service.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { createAbortError, isAbortError, throwIfAborted } from '@core/errors/abort.ts';
import { i18n } from '@core/i18n/index.ts';
import { runOpenAiModelTestStream } from '@core/openai/modelTestStreamClient.ts';
import { ModelTestStreamError, readModelTestStreamFailureOutcome, type ModelTestFailureMetadata } from '@core/openai/modelTestStreamOutcome.ts';
import type { AiSetupModel, AiSetupState, AiSetupTestOutcome } from '@core/storage/aisetup/aiSetupTypes.ts';
import { wallClockMs } from '@core/time/clock.ts';
import { MODEL_CONTEXT_WINDOW_PARAMETER_KEY, type ModelData } from '@core/types/modelTypes.ts';
import { createWebSocketRunId } from '@core/websocketclient/runCorrelation.ts';
import { findItemModel, readConfigurationFingerprint, readModelOperationId } from '@pages/wizard/services/aisetup/catalog/mappers.ts';
import type { ReadinessPhase } from '@pages/wizard/services/aisetup/progress/mappers.ts';
import { withConfiguration, withModelDiscovered, withTestResult, withTestStale } from '@pages/wizard/services/aisetup/state.ts';

const MODEL_TEST_TIMEOUT_MS = 60_000;
const MODEL_TEST_LOADING_TIMEOUT_MS = 7_200_000;
const UNVERSIONED_CONFIGURATION = '0';

interface AiSetupReadinessManagerHost {
    getSetup(): AiSetupState;
    updateSetup(update: (setup: AiSetupState) => AiSetupState): void;
    getModels(): readonly ModelData[];
    resolveStarterContextTokens(item: AiSetupModel): number | null;
    refreshModels(): Promise<readonly ModelData[]>;
    onChange(): void;
}

const isConfigurationChanged = (item: AiSetupModel, model: ModelData): boolean => {
    if (item.source !== 'local' || item.test.status !== 'passed') return false;
    const fingerprint = readConfigurationFingerprint(model);
    return fingerprint !== null && fingerprint !== item.test.configurationFingerprint;
};

class AiSetupReadinessManager {
    readonly #host: AiSetupReadinessManagerHost;
    readonly #phases = new Map<string, ReadinessPhase>();
    readonly #requestedTests = new Set<string>();
    readonly #abortController = new AbortController();
    #localRunning = false;

    constructor(host: AiSetupReadinessManagerHost) {
        this.#host = host;
    }

    get phases(): ReadonlyMap<string, ReadinessPhase> {
        return this.#phases;
    }

    dispose(): void {
        this.#abortController.abort();
    }

    schedule(): void {
        if (this.#abortController.signal.aborted) return;
        if (this.#host.getSetup().step !== 'ai_progress') return;
        const models = this.#host.getModels();
        for (const item of this.#host.getSetup().models) {
            const model = item.excluded ? null : findItemModel(models, item);
            if (model !== null && item.modelId === null) this.#host.updateSetup((setup) => withModelDiscovered(setup, item.itemId, model.id));
            if (model !== null && isConfigurationChanged(item, model)) this.#host.updateSetup((setup) => withTestStale(setup, item.itemId));
        }
        if (this.#localRunning) return;
        const next = this.#host.getSetup().models.find((item) => this.#isLocalCandidate(item, models));
        if (next === undefined) return;
        this.#localRunning = true;
        void this.#prepareLocal(next.itemId)
            .catch((error) => {
                this.#phases.delete(next.itemId);
                if (this.#abortController.signal.aborted || isAbortError(error)) return;
                this.#host.updateSetup((setup) => withTestResult(setup, next.itemId, 'load_error', null, wallClockMs()));
                this.#host.onChange();
                errorHandler.error('WizardAiSetup', 'Local model readiness check failed', ensureError(error));
            })
            .finally(() => {
                this.#localRunning = false;
                this.schedule();
            });
    }

    requestTest(itemId: string): void {
        if (this.#abortController.signal.aborted) return;
        const item = this.#host.getSetup().models.find((entry) => entry.itemId === itemId) ?? null;
        if (item === null || item.excluded || this.#phases.has(itemId)) return;
        if (item.source === 'local') {
            this.#requestedTests.add(itemId);
            this.schedule();
            return;
        }
        void this.#runTest(item).catch((error) => errorHandler.error('WizardAiSetup', 'Cloud model test failed', ensureError(error)));
    }

    #isLocalCandidate(item: AiSetupModel, models: readonly ModelData[]): boolean {
        if (item.source !== 'local' || item.excluded || this.#phases.has(item.itemId) || findItemModel(models, item) === null) return false;
        if (this.#requestedTests.has(item.itemId)) return true;
        return item.test.status === 'not_run';
    }

    async #prepareLocal(itemId: string): Promise<void> {
        this.#requestedTests.delete(itemId);
        const item = this.#requireItem(itemId);
        if (item.test.configurationFingerprint === null) {
            this.#setPhase(itemId, 'configuring');
            const fingerprint = await this.#applyStarterSettings(item);
            this.#ensureLocalActive(itemId);
            this.#host.updateSetup((setup) => withConfiguration(setup, itemId, fingerprint));
        }
        this.#ensureLocalActive(itemId);
        await this.#runTest(this.#requireItem(itemId));
    }

    async #applyStarterSettings(item: AiSetupModel): Promise<string> {
        const models = await this.#host.refreshModels();
        this.#ensureLocalActive(item.itemId);
        const model = findItemModel(models, item);
        if (model === null) throw new Error('AI setup model is unavailable during configuration');
        const contextTokens = this.#host.resolveStarterContextTokens(item);
        if (contextTokens === null || model.modelHasCustomParameters === true) return readConfigurationFingerprint(model) ?? UNVERSIONED_CONFIGURATION;
        await getApiClient().models.updateParameters(readModelOperationId(model), { [MODEL_CONTEXT_WINDOW_PARAMETER_KEY]: contextTokens });
        throwIfAborted(this.#abortController.signal);
        const refreshed = await this.#host.refreshModels();
        throwIfAborted(this.#abortController.signal);
        const current = findItemModel(refreshed, item);
        if (current === null || current.contextWindowTokens !== contextTokens) throw new Error('AI setup starter settings were not confirmed by the model catalog');
        const fingerprint = readConfigurationFingerprint(current);
        if (fingerprint === null) throw new Error('AI setup model configuration revision is unavailable');
        return fingerprint;
    }

    #ensureLocalActive(itemId: string): void {
        throwIfAborted(this.#abortController.signal);
        if (this.#requireItem(itemId).excluded || this.#host.getSetup().step !== 'ai_progress') throw createAbortError();
    }

    async #runTest(item: AiSetupModel): Promise<void> {
        throwIfAborted(this.#abortController.signal);
        const model = this.#requireModel(item);
        const fingerprint = readConfigurationFingerprint(model) ?? item.test.configurationFingerprint;
        this.#setPhase(item.itemId, 'testing');
        let outcome: AiSetupTestOutcome;
        let failure: ModelTestFailureMetadata | null = null;
        const testedRecord = item.test;
        try {
            outcome = await runOpenAiModelTestStream({
                runId: createWebSocketRunId('ws_ai_setup_test'),
                request: { model: readModelOperationId(model), stream: true, reasoningEffort: 'none', messages: [{ role: 'user', content: i18n.t('wizard.aiSetup.progress.testPrompt') }] },
                signal: this.#abortController.signal,
                cancelReason: i18n.t('wizard.aiSetup.progress.testCancelled'),
                timeoutMs: MODEL_TEST_TIMEOUT_MS,
                loadingTimeoutMs: MODEL_TEST_LOADING_TIMEOUT_MS,
                errorMessageFallback: i18n.t('wizard.aiSetup.progress.error.loadError'),
                onAssistantTextDelta: () => undefined
            });
        } catch (error) {
            const runtimeError = ensureError(error);
            outcome = readModelTestStreamFailureOutcome(runtimeError);
            failure = runtimeError instanceof ModelTestStreamError ? runtimeError.failure : null;
        } finally {
            this.#phases.delete(item.itemId);
        }
        if (this.#abortController.signal.aborted) return;
        this.#host.updateSetup((setup) => {
            const current = setup.models.find((entry) => entry.itemId === item.itemId);
            if (!current || current.excluded || current.modelId !== item.modelId || current.pluginName !== item.pluginName || current.artifactReference !== item.artifactReference || current.repositoryId !== item.repositoryId) return setup;
            if (current.test.status !== testedRecord.status || current.test.outcome !== testedRecord.outcome || current.test.testedAtMs !== testedRecord.testedAtMs || current.test.configurationFingerprint !== testedRecord.configurationFingerprint) return setup;
            const currentModel = findItemModel(this.#host.getModels(), current);
            if (currentModel === null || readModelOperationId(currentModel) !== readModelOperationId(model) || (readConfigurationFingerprint(currentModel) ?? current.test.configurationFingerprint) !== fingerprint) return setup;
            return withTestResult(setup, item.itemId, outcome, fingerprint, wallClockMs(), failure);
        });
        this.#host.onChange();
    }

    #setPhase(itemId: string, phase: ReadinessPhase): void {
        this.#phases.set(itemId, phase);
        this.#host.onChange();
    }

    #requireItem(itemId: string): AiSetupModel {
        const item = this.#host.getSetup().models.find((entry) => entry.itemId === itemId);
        if (item === undefined) throw createAbortError(`AI setup item ${itemId} was removed`);
        return item;
    }

    #requireModel(item: AiSetupModel): ModelData {
        const model = findItemModel(this.#host.getModels(), item);
        if (model === null) throw new Error(`AI setup model for item ${item.itemId} is not in the model catalog`);
        return model;
    }
}

export { AiSetupReadinessManager };
export type { AiSetupReadinessManagerHost };
