/* SoAI - Wizard AI setup user interactions [frontend/assets/ts/pages/wizard/services/aisetup/AiSetupInteractionsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { optionalNonNegativeIntegerDataAttribute } from '@core/dom/attributes.ts';
import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { AiSetupState } from '@core/storage/aisetup/aiSetupTypes.ts';
import type { AiSetupWizardStepId } from '@features/wizard/public.ts';
import { AI_ENGINE_INPUT_NAME, AI_ENGINE_MODE_INPUT_NAME, AI_PROVIDER_FORM_ID } from '@pages/wizard/rendering/aisetup/connect/view.ts';
import { AI_CLOUD_FILTER_ID, AI_FIRST_CHAT_INPUT_NAME, AI_MODEL_INPUT_NAME, AI_SEARCH_FORM_ID, parseSelectionKey } from '@pages/wizard/rendering/aisetup/models/view.ts';
import { AI_SOURCE_INPUT_NAME } from '@pages/wizard/rendering/aisetup/sources/view.ts';
import type { AiSetupActionId } from '@pages/wizard/actions.ts';
import type { AiSetupController } from '@pages/wizard/services/aisetup/AiSetupController.ts';
import { resolveSearchPluginName } from '@pages/wizard/services/aisetup/facts/service.ts';
import type { ProviderDraft } from '@pages/wizard/services/aisetup/AiSetupCloudConnectionSession.ts';
import { readBackendRowPlugin } from '@pages/wizard/services/aisetup/progress/mappers.ts';
import { activeProvider, withBackendExcluded, withCloudSelection, withEngineChoice, withFirstChat, withItemExcluded, withLocalSelection, withSources, type LocalModelPick } from '@pages/wizard/services/aisetup/state.ts';
import { findModelCatalogEntry } from '@pages/wizard/services/aisetup/catalog/constants.ts';

interface AiSetupInteractionsFlowPort {
    readonly stepUi: { readonly stepId: AiSetupWizardStepId | null };
    refreshNow(): void;
    scheduleRefresh(): void;
}

interface AiSetupInteractionsControllerHost {
    controller: AiSetupController;
    flow: AiSetupInteractionsFlowPort;
    goToStep(stepId: AiSetupWizardStepId): void;
    syncSteps(): void;
    syncNavigation(): void;
    focusCloudError(): void;
    openModelSearch(): void;
    revealSearchVariants(): void;
    requireContent(): HTMLElement;
}

const readFormValue = (form: HTMLFormElement, name: string): string => {
    const field = form.elements.namedItem(name);
    return field instanceof HTMLInputElement || field instanceof HTMLSelectElement ? field.value : '';
};

const readLocalPicks = (setup: AiSetupState): LocalModelPick[] => setup.models.flatMap((model) => (model.source === 'local' && !model.excluded && model.repositoryId !== null && model.artifactReference !== null ? [{ catalogId: model.catalogId, pluginName: model.pluginName, repositoryId: model.repositoryId, artifactReference: model.artifactReference, artifactName: model.artifactName ?? model.artifactReference }] : []));

const resolveSelectionItemId = (setup: AiSetupState, key: string): string | null => {
    const { type, value } = parseSelectionKey(key);
    const models = setup.models.filter((model) => !model.excluded);
    if (type === 'catalog') return models.find((model) => model.source === 'local' && model.catalogId === value)?.itemId ?? null;
    if (type === 'cloud') return models.find((model) => model.source === 'cloud' && model.modelId === value)?.itemId ?? null;
    return models.find((model) => model.itemId === value)?.itemId ?? null;
};

class AiSetupInteractionsController {
    readonly #host: AiSetupInteractionsControllerHost;

    constructor(host: AiSetupInteractionsControllerHost) {
        this.#host = host;
    }

    handleInput(target: EventTarget | null): void {
        if (!(target instanceof HTMLInputElement) && !(target instanceof HTMLSelectElement)) return;
        const controller = this.#host.controller;
        if (target.name === AI_SOURCE_INPUT_NAME && target instanceof HTMLInputElement) {
            const checked = target.checked;
            const isCloud = target.value === 'cloud';
            controller.updateSetup((setup) => withSources(setup, { local: isCloud ? setup.sources.local : checked, cloud: isCloud ? checked : setup.sources.cloud }));
            this.#host.syncSteps();
        } else if (target.name === AI_ENGINE_MODE_INPUT_NAME) {
            this.#applyEngineChoice([]);
        } else if (target.name === AI_ENGINE_INPUT_NAME) {
            this.#applyEngineChoice(dom.resolveAll(`input[name="${AI_ENGINE_INPUT_NAME}"]:checked`, this.#host.requireContent()).flatMap((input) => (input instanceof HTMLInputElement ? [input.value] : [])));
        } else if (target.name === AI_MODEL_INPUT_NAME && target instanceof HTMLInputElement) {
            this.#toggleModel(target.value, target.checked);
        } else if (target.name === AI_FIRST_CHAT_INPUT_NAME) {
            controller.updateSetup((setup) => withFirstChat(setup, resolveSelectionItemId(setup, target.value)));
        } else if (target.id === AI_CLOUD_FILTER_ID) {
            controller.cloudFilter = target.value;
        } else if (target.form?.id === AI_PROVIDER_FORM_ID) {
            controller.cloud.rememberDraft(this.#readProviderForm(target.form));
            return;
        } else {
            return;
        }
        this.#refresh();
    }

    handleSubmit(form: HTMLFormElement): boolean {
        if (form.id === AI_PROVIDER_FORM_ID) {
            this.#run('provider connection', this.#connect(form));
            return true;
        }
        if (form.id === AI_SEARCH_FORM_ID) {
            this.#host.controller.searchOpen = true;
            this.#run('model search', this.#host.controller.search.search(this.#searchPluginName(), readFormValue(form, 'query')));
            return true;
        }
        return false;
    }

    execute(action: AiSetupActionId, source: HTMLElement): void {
        const controller = this.#host.controller;
        switch (action) {
            case 'wizard-ai-change-provider':
                controller.cloud.edit();
                return;
            case 'wizard-ai-use-cloud':
                controller.updateSetup((setup) => withSources(setup, { ...setup.sources, cloud: true }));
                this.#host.syncSteps();
                this.#host.goToStep('ai_connect');
                return;
            case 'wizard-ai-back-to-provider':
                controller.cloud.edit();
                this.#host.goToStep('ai_connect');
                return;
            case 'wizard-ai-search-manually':
                this.#openSearch();
                return;
            case 'wizard-ai-search-result':
                this.#run('model variant probe', this.#selectSearchResult(optionalNonNegativeIntegerDataAttribute(source, 'result-index', 'AI setup search result') ?? -1));
                return;
            case 'wizard-ai-search-variant':
                this.#addVariant(optionalNonNegativeIntegerDataAttribute(source, 'variant-index', 'AI setup variant') ?? -1);
                return;
            case 'wizard-ai-row-action':
                this.#runRowAction(source.dataset['aiRowAction'] ?? '', source.dataset['aiRow'] ?? '');
                return;
            case 'wizard-ai-retry-load':
                if (this.#host.flow.stepUi.stepId !== null) this.#host.goToStep(this.#host.flow.stepUi.stepId);
                return;
        }
    }

    async #connect(form: HTMLFormElement): Promise<void> {
        const connected = await this.#host.controller.cloud.connect({ ...this.#readProviderForm(form), apiKey: readFormValue(form, 'api-key') });
        this.#host.flow.refreshNow();
        if (!connected) this.#host.focusCloudError();
    }

    #readProviderForm(form: HTMLFormElement): ProviderDraft {
        return { pluginName: readFormValue(form, 'plugin'), name: readFormValue(form, 'provider-name'), apiUrl: readFormValue(form, 'api-url'), modelsFilter: readFormValue(form, 'models-filter') };
    }

    #applyEngineChoice(pluginNames: readonly string[]): void {
        const controller = this.#host.controller;
        const facts = controller.requireFacts();
        if (pluginNames.length === 0) {
            const automatic = facts.automatic;
            controller.updateSetup((setup) => withEngineChoice(setup, 'automatic', automatic.status === 'install' ? [{ pluginName: automatic.pluginName, variantId: automatic.variantId }] : []));
            return;
        }
        const choices = facts.engineOptions.flatMap((option) => (pluginNames.includes(option.pluginName) && option.engine.status === 'install' ? [{ pluginName: option.pluginName, variantId: option.engine.variantId }] : []));
        const installed = facts.engineOptions.flatMap((option) => (pluginNames.includes(option.pluginName) && option.engine.status === 'installed' ? [{ pluginName: option.pluginName, variantId: option.engine.variantId }] : []));
        controller.updateSetup((setup) => withEngineChoice(setup, 'manual', [...installed, ...choices]));
    }

    #toggleModel(key: string, selected: boolean): void {
        const controller = this.#host.controller;
        const { type, value } = parseSelectionKey(key);
        const setup = controller.requireSetup();
        if (type === 'cloud') {
            const provider = activeProvider(setup);
            if (provider === null) return;
            const current = setup.models.filter((model) => model.source === 'cloud' && !model.excluded && model.modelId !== null && model.modelId !== value).map((model) => ({ pluginName: model.pluginName, modelId: model.modelId ?? '' }));
            this.#applySelection(() => controller.updateSetup((state) => withCloudSelection(state, selected ? [...current, { pluginName: provider.pluginName, modelId: value }] : current)));
            return;
        }
        const picks = readLocalPicks(setup);
        const entry = type === 'catalog' ? findModelCatalogEntry(value) : null;
        const pick: LocalModelPick | null = entry === null ? null : { catalogId: entry.id, pluginName: entry.pluginName, repositoryId: entry.repository, artifactReference: entry.file, artifactName: entry.file };
        const itemId = resolveSelectionItemId(setup, key);
        const item = setup.models.find((model) => model.itemId === itemId) ?? null;
        const remaining = picks.filter((candidate) => item === null || candidate.repositoryId !== item.repositoryId || candidate.artifactReference !== item.artifactReference);
        this.#applySelection(() => controller.updateSetup((state) => withLocalSelection(state, selected && pick !== null ? [...remaining, pick] : remaining)));
    }

    #addVariant(index: number): void {
        const controller = this.#host.controller;
        const pick = controller.search.readVariantPick(this.#searchPluginName(), index);
        if (pick === null) return;
        this.#applySelection(() => controller.updateSetup((state) => withLocalSelection(state, [...readLocalPicks(state), pick])));
        this.#refresh();
    }

    #applySelection(apply: () => void): void {
        try {
            apply();
        } catch (error) {
            const runtimeError = ensureError(error);
            if (!(runtimeError instanceof RangeError)) throw runtimeError;
            errorHandler.warn('WizardAiSetup', 'AI setup selection limit reached', runtimeError);
        }
    }

    #runRowAction(action: string, rowKey: string): void {
        const controller = this.#host.controller;
        const setup = controller.requireSetup();
        const item = setup.models.find((model) => model.itemId === rowKey) ?? null;
        const backendPlugin = readBackendRowPlugin(rowKey);
        if (action === 'skip') {
            controller.updateSetup((state) => (backendPlugin === null ? withItemExcluded(state, rowKey) : withBackendExcluded(state, backendPlugin)));
        } else if (action === 'retry_installation') {
            controller.operations.retryInstall(backendPlugin ?? item?.pluginName ?? '');
        } else if (action === 'check_again' && item !== null) {
            controller.operations.checkAgain(item.itemId);
        } else if (action === 'retry' && item !== null && item.test.status !== 'failed') {
            controller.operations.retryDownload(item.itemId);
        } else if (item !== null) {
            controller.readiness.requestTest(item.itemId);
        }
        this.#refresh();
    }

    #openSearch(): void {
        this.#host.controller.searchOpen = true;
        this.#host.openModelSearch();
    }

    async #selectSearchResult(index: number): Promise<void> {
        await this.#host.controller.search.selectResult(this.#searchPluginName(), index);
        this.#host.flow.refreshNow();
        this.#host.revealSearchVariants();
    }

    #searchPluginName(): string {
        return resolveSearchPluginName(this.#host.controller.requireFacts(), this.#host.controller.requireSetup());
    }

    #refresh(): void {
        this.#host.flow.scheduleRefresh();
        this.#host.syncNavigation();
    }

    #run(operation: string, task: Promise<void>): void {
        void task.catch((error) => errorHandler.error('WizardAiSetup', `AI setup ${operation} failed`, ensureError(error)));
    }
}

export { AiSetupInteractionsController };
export type { AiSetupInteractionsControllerHost };
