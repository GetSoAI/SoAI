/* SoAI - Staged chat configuration model-set state [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/ConfigurationModelSelectionStateManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import { i18n } from '@core/i18n/index.ts';
import { isChatSelectableModel } from '@core/models/chatModelAvailability.ts';
import { isOpenAICapabilityEnabled } from '@core/openai/capabilityChecks.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import { normalizeComparisonModelIds } from '@core/chat/comparisonModels.ts';
import { normalizeChatModelId, type EffectiveModels } from '@pages/chat/controllers/chatmodelcontrol/chatModelControlStateManager.ts';
import { resolveVoiceModelAvailability, type VoiceModelAvailability } from '@pages/chat/controllers/chatconfigurationcontroller/chatPresetModelValidationDomain.ts';
import { dom } from '@core/dom/dom.ts';

type ConfigurationModelSnapshot = Readonly<{ model: string | null; selectable: boolean; supportsToolCalling: boolean; voiceModelAvailability: VoiceModelAvailability }>;
const MODEL_SELECTION_FIELD_KEY = 'configuration-model-selection';
const MODEL_CONTROL_ROOT_SELECTOR = '[data-chat-model-control="true"][data-scope="configuration"]';

interface ConfigurationModelSelectionStateHost {
    root: Element;
    getModels(): readonly ModelData[];
    getModelIndex(): ReadonlyMap<string, ModelData>;
    hasModelCatalog(): boolean;
    isSelectionLocked(): boolean;
}

const copyModels = (models: EffectiveModels): EffectiveModels => ({ primary: models.primary, comparison: [...models.comparison] });

const areModelSetsEqual = (first: EffectiveModels, second: EffectiveModels): boolean => {
    if (first.primary !== second.primary || first.comparison.length !== second.comparison.length) {
        return false;
    }
    return first.comparison.every((modelId, index) => modelId === second.comparison[index]);
};

class ConfigurationModelSelectionStateManager {
    readonly #host: ConfigurationModelSelectionStateHost;
    readonly #fieldState: FieldStateTracker;
    #baseline: EffectiveModels = { primary: null, comparison: [] };
    #working: EffectiveModels = { primary: null, comparison: [] };
    #editing = false;

    constructor(host: ConfigurationModelSelectionStateHost) {
        this.#host = host;
        this.#fieldState = new FieldStateTracker({ getElement: () => dom.resolve(MODEL_CONTROL_ROOT_SELECTOR, this.#host.root) });
    }

    begin(models: EffectiveModels): void {
        const normalized = this.#normalize(models);
        this.#baseline = normalized;
        this.#working = copyModels(normalized);
        this.#editing = true;
        this.#syncFieldState();
    }

    cancel(): void {
        this.#editing = false;
        this.#baseline = { primary: null, comparison: [] };
        this.#working = { primary: null, comparison: [] };
        this.#fieldState.clearAll();
    }

    rebase(models: EffectiveModels = this.#working): void {
        const normalized = this.#normalize(models);
        this.#baseline = normalized;
        this.#working = copyModels(normalized);
        this.#syncFieldState();
    }

    snapshot(modelId: string | null = this.#working.primary): ConfigurationModelSnapshot {
        const model = modelId ? this.#host.getModelIndex().get(modelId) : null;
        return Object.freeze({ model: modelId, selectable: Boolean(model && isChatSelectableModel(model)), supportsToolCalling: isOpenAICapabilityEnabled(model?.openaiCapabilities, 'chat_features', 'tool_calling'), voiceModelAvailability: resolveVoiceModelAvailability(this.#host.getModels()) });
    }

    workingModels(): EffectiveModels {
        return copyModels(this.#working);
    }

    workingModel(): string | null {
        return this.#working.primary;
    }

    workingComparisonModels(): string[] {
        return [...this.#working.comparison];
    }

    baselineModel(): string | null {
        return this.#baseline.primary;
    }

    isCatalogHydrated(): boolean {
        return this.#host.hasModelCatalog();
    }

    isDirty(): boolean {
        return this.#editing && !areModelSetsEqual(this.#working, this.#baseline);
    }

    isValid(): boolean {
        return !this.isDirty() || this.#isSelectableModelSet(this.#working);
    }

    canCommitSnapshot(snapshot: ConfigurationModelSnapshot): boolean {
        const candidate = this.#normalize({ primary: snapshot.model, comparison: this.#working.comparison });
        return !this.#host.isSelectionLocked() && snapshot.selectable && this.#isSelectableModelSet(candidate);
    }

    commitSnapshot(snapshot: ConfigurationModelSnapshot): void {
        if (!this.canCommitSnapshot(snapshot)) {
            throw new Error('Chat configuration preset model cannot be staged.');
        }
        this.#working = this.#normalize({ primary: snapshot.model, comparison: this.#working.comparison });
        this.#syncFieldState();
    }

    stage(models: EffectiveModels): void {
        if (!this.#editing || this.#host.isSelectionLocked()) {
            return;
        }
        const normalized = this.#normalize(models);
        if (!this.#isSelectableModelSet(normalized)) {
            throw new Error('Chat configuration model selection must contain selectable models.');
        }
        this.#working = normalized;
        this.#syncFieldState();
    }

    refreshPresentation(): void {
        this.#syncFieldState();
    }

    #isSelectableModelSet(models: EffectiveModels): boolean {
        if (!models.primary) {
            return false;
        }
        return [models.primary, ...models.comparison].every((modelId) => {
            const model = this.#host.getModelIndex().get(modelId);
            return Boolean(model && isChatSelectableModel(model));
        });
    }

    #hasUnavailableWorkingModels(): boolean {
        if (!this.#host.hasModelCatalog()) {
            return false;
        }
        return [this.#working.primary, ...this.#working.comparison].some((modelId) => {
            if (!modelId) {
                return false;
            }
            const model = this.#host.getModelIndex().get(modelId);
            return !model || !isChatSelectableModel(model);
        });
    }

    #syncFieldState(): void {
        this.#fieldState.update(MODEL_SELECTION_FIELD_KEY, { currentValue: JSON.stringify(this.#working), originalValue: JSON.stringify(this.#baseline) });
        this.#fieldState.setInvalid(MODEL_SELECTION_FIELD_KEY, this.#hasUnavailableWorkingModels() ? i18n.t('chat.configuration.configurationModel.unavailable') : null);
    }

    #normalize(models: EffectiveModels): EffectiveModels {
        const primary = normalizeChatModelId(models.primary);
        const comparison = normalizeComparisonModelIds({ primaryModelId: primary, raw: models.comparison });
        return { primary, comparison };
    }
}

export { ConfigurationModelSelectionStateManager };
export type { ConfigurationModelSnapshot };
