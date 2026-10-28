/* SoAI - Wizard AI setup step flow and navigation [frontend/assets/ts/pages/wizard/services/aisetup/AiSetupFlowController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { AI_SETUP_STEPS, type AiSetupDisposition, type AiSetupState } from '@core/storage/aisetup/aiSetupTypes.ts';
import { requireTaskOperationsApi } from '@core/tasks/serviceAccess.ts';
import type { AiSetupWizardStepId } from '@features/wizard/public.ts';
import { MODEL_DOWNLOAD_OPERATION_TYPE } from '@features/models/public.ts';
import type { AiSetupViewModel } from '@pages/wizard/contracts/aisetup/types.ts';
import type { PageStreamingContract } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { AiSetupStepUiController, type AiSetupStepUiControllerHost } from '@pages/wizard/controllers/AiSetupStepUiController.ts';
import { AiSetupController, type AiSetupStorage } from '@pages/wizard/services/aisetup/AiSetupController.ts';
import { AiSetupInteractionsController } from '@pages/wizard/services/aisetup/AiSetupInteractionsController.ts';
import { isAiSetupDiscoveryReady, isEngineInstalled, resolveRecommendations, resolveSearchPluginName } from '@pages/wizard/services/aisetup/facts/service.ts';
import { backendRowKey, isRowReady } from '@pages/wizard/services/aisetup/progress/mappers.ts';
import { BACKEND_INSTALL_OPERATION_TYPE } from '@pages/wizard/services/aisetup/AiSetupOperationsManager.ts';
import { activeProvider, resolveHandoffItemId, selectedModels, withDisposition, withEngineChoice, withHandoff, withLocalSelection, withLocalDownloadCommitted, withStepReached } from '@pages/wizard/services/aisetup/state.ts';
import { buildCompletionView, buildConnectView, buildModelsView, buildSourcesView } from '@pages/wizard/services/aisetup/mappers.ts';

interface AiSetupFlowControllerHost {
    streaming: PageStreamingContract;
    storage: AiSetupStorage;
    view: Omit<AiSetupStepUiControllerHost, 'cancelRow'>;
    requireContent(): HTMLElement;
    syncSteps(): void;
    syncNavigation(): void;
    goToStep(stepId: AiSetupWizardStepId): void;
    skip(): void;
    notify(message: string, type: NotificationType): void;
}

const pendingInstalls = (setup: AiSetupState, controller: AiSetupController): { pluginName: string; variantId: string }[] => {
    const facts = controller.requireFacts();
    return setup.engine.backends.filter((backend) => !backend.excluded && backend.taskId === null && !isEngineInstalled(facts, backend.pluginName) && !controller.operations.observations.has(backendRowKey(backend.pluginName)));
};

const hasLocalChoice = (setup: AiSetupState, controller: AiSetupController): boolean => {
    const facts = controller.requireFacts();
    if (setup.engine.mode === 'automatic') return facts.automatic.status !== 'none';
    return setup.engine.backends.some((backend) => !backend.excluded && facts.engineOptions.some((option) => option.pluginName === backend.pluginName && option.engine.status !== 'none'));
};

class AiSetupFlowController {
    readonly #host: AiSetupFlowControllerHost;
    readonly controller: AiSetupController;
    readonly stepUi: AiSetupStepUiController;
    readonly interactions: AiSetupInteractionsController;
    readonly #frames = new ResourceTracker();
    #refreshScheduled = false;
    #loadFailed = false;

    constructor(host: AiSetupFlowControllerHost) {
        this.#host = host;
        this.controller = new AiSetupController({ streaming: host.streaming, storage: host.storage, onChange: () => this.scheduleRefresh(), notify: (message, type) => host.notify(message, type) });
        this.stepUi = new AiSetupStepUiController({ ...host.view, cancelRow: (key) => this.controller.operations.cancel(key) });
        this.interactions = new AiSetupInteractionsController({
            controller: this.controller,
            flow: this,
            goToStep: (stepId) => host.goToStep(stepId),
            skip: () => host.skip(),
            syncSteps: () => host.syncSteps(),
            syncNavigation: () => host.syncNavigation(),
            focusCloudError: () => this.stepUi.focusCloudError(),
            openModelSearch: () => this.stepUi.openModelSearch(),
            requireContent: () => host.requireContent()
        });
    }

    async prepareStep(stepId: AiSetupWizardStepId | 'complete'): Promise<void> {
        const controller = this.controller;
        if (stepId === 'complete') {
            if (controller.setup !== null) this.#loadFailed = !(await this.#activate());
            return;
        }
        this.#loadFailed = !(await this.#activate());
        const setup = controller.ensureSetup();
        const arrivingForward = AI_SETUP_STEPS.indexOf(setup.step) < AI_SETUP_STEPS.indexOf(stepId);
        if (arrivingForward && !this.#loadFailed) controller.updateSetup((current) => withStepReached(current, stepId));
        if (stepId === 'ai_models' && !this.#loadFailed) {
            if (arrivingForward) this.#preselectTopRecommendation();
            controller.search.bindEngine(resolveSearchPluginName(controller.requireFacts(), controller.requireSetup()));
        }
        this.#host.syncSteps();
    }

    async #activate(): Promise<boolean> {
        try {
            return isAiSetupDiscoveryReady(await this.controller.activate());
        } catch (error) {
            const runtimeError = ensureError(error);
            if (isAbortError(runtimeError)) throw runtimeError;
            errorHandler.warn('WizardAiSetup', 'AI setup facts could not be loaded', runtimeError);
            return false;
        }
    }

    #preselectTopRecommendation(): void {
        const controller = this.controller;
        const setup = controller.requireSetup();
        if (!setup.sources.local || setup.models.some((model) => model.source === 'local')) return;
        const top = resolveRecommendations(controller.requireFacts(), setup).cards[0];
        if (top === undefined) return;
        controller.updateSetup((current) => withLocalSelection(current, [{ catalogId: top.entry.id, pluginName: top.entry.pluginName, repositoryId: top.entry.repository, artifactReference: top.entry.file, artifactName: top.entry.file }]));
    }

    buildViewModel(stepId: AiSetupWizardStepId | 'complete'): AiSetupViewModel | null {
        if (this.controller.setup === null) return null;
        if (!this.#hasCompleteFacts()) return { loadFailed: stepId !== 'complete', sources: null, connect: null, models: null, progress: null, completion: null };
        const snapshot = this.controller.snapshot();
        return {
            loadFailed: false,
            sources: stepId === 'ai_sources' ? buildSourcesView(snapshot) : null,
            connect: stepId === 'ai_connect' ? buildConnectView(snapshot) : null,
            models: stepId === 'ai_models' ? buildModelsView(snapshot) : null,
            progress: stepId === 'ai_progress' ? snapshot.progress : null,
            completion: stepId === 'complete' && snapshot.setup.models.some((model) => !model.excluded) ? buildCompletionView(snapshot.progress) : null
        };
    }

    afterRender(stepId: AiSetupWizardStepId, content: HTMLElement): void {
        this.stepUi.attach(stepId, content);
        this.#syncStepUi();
    }

    readonly scheduleRefresh = (): void => {
        if (this.#refreshScheduled) return;
        this.#refreshScheduled = true;
        this.#frames.requestAnimationFrame(() => {
            this.#refreshScheduled = false;
            this.refreshNow();
        });
    };

    refreshNow(): void {
        this.#syncStepUi();
        this.#host.syncNavigation();
    }

    canContinue(stepId: AiSetupWizardStepId): boolean {
        const controller = this.controller;
        const setup = controller.setup;
        if (setup === null || !this.#hasCompleteFacts()) return false;
        if (stepId === 'ai_sources') return setup.sources.local || setup.sources.cloud;
        if (stepId === 'ai_connect') return (!setup.sources.cloud || activeProvider(setup) !== null) && (!setup.sources.local || hasLocalChoice(setup, controller)) && !controller.cloud.state.connecting;
        if (stepId === 'ai_models') return selectedModels(setup).length > 0 && selectedModels(setup).filter((model) => model.source === 'local').length <= 1;
        return this.hasReadyModel();
    }

    nextLabel(stepId: AiSetupWizardStepId): string {
        const setup = this.controller.setup;
        if (setup !== null && stepId === 'ai_connect' && setup.sources.local && this.controller.facts !== null && pendingInstalls(setup, this.controller).length > 0) return i18n.t('wizard.aiSetup.nav.installAndContinue');
        if (setup !== null && stepId === 'ai_models' && selectedModels(setup).some((model) => model.source === 'local' && model.downloadTaskId === null && model.modelId === null)) return i18n.t('wizard.aiSetup.nav.downloadAndContinue');
        if (stepId === 'ai_progress') return i18n.t('wizard.aiSetup.nav.startChatting');
        return i18n.t('wizard.aiSetup.nav.continue');
    }

    continueFrom(stepId: AiSetupWizardStepId): void {
        const controller = this.controller;
        if (stepId === 'ai_sources') {
            const setup = controller.requireSetup();
            const facts = controller.requireFacts();
            if (setup.engine.mode === 'automatic') {
                const automatic = facts.automatic;
                controller.updateSetup((current) => withEngineChoice(current, 'automatic', current.sources.local && automatic.status === 'install' ? [{ pluginName: automatic.pluginName, variantId: automatic.variantId }] : []));
            }
            this.#host.syncSteps();
            return;
        }
        if (stepId === 'ai_connect') {
            for (const backend of pendingInstalls(controller.requireSetup(), controller)) controller.operations.startInstall(backend.pluginName, backend.variantId);
            return;
        }
        if (stepId === 'ai_models') {
            controller.updateSetup((setup) => withLocalDownloadCommitted(setup));
            controller.operations.startPendingDownloads();
            controller.readiness.schedule();
        }
    }

    hasReadyModel(): boolean {
        const controller = this.controller;
        if (controller.setup === null) return false;
        const progress = controller.progress();
        return progress.readyCount > 0;
    }

    leave(disposition: AiSetupDisposition): void {
        const controller = this.controller;
        if (controller.setup === null) return;
        controller.updateSetup((setup) => withDisposition(setup, disposition));
        const notice = this.#readBackgroundNotice(controller.requireSetup());
        if (notice !== null) this.#host.notify(notice, 'warning');
    }

    prepareHandoff(): string | null {
        const controller = this.controller;
        const progress = controller.progress();
        const itemId = resolveHandoffItemId(controller.requireSetup(), (model) => isRowReady(progress, model.itemId));
        if (itemId === null) return null;
        this.leave(progress.readyCount === progress.modelCount ? 'completed' : 'handed_off');
        controller.updateSetup((setup) => withHandoff(setup, true, itemId));
        return itemId;
    }

    destroy(): void {
        this.#frames.cleanup();
        this.stepUi.detach();
        this.controller.destroy();
    }

    #syncStepUi(): void {
        const controller = this.controller;
        const stepId = this.stepUi.stepId;
        if (stepId === null || controller.setup === null) return;
        if (!this.#hasCompleteFacts()) {
            this.stepUi.syncLoadFailed();
            return;
        }
        const snapshot = controller.snapshot();
        if (stepId === 'ai_connect') this.stepUi.syncConnect(buildConnectView(snapshot));
        if (stepId === 'ai_models') this.stepUi.syncModels(buildModelsView(snapshot));
        if (stepId === 'ai_progress') this.stepUi.syncProgress(snapshot.progress);
    }

    #hasCompleteFacts(): boolean {
        const facts = this.controller.facts;
        return !this.#loadFailed && facts !== null && isAiSetupDiscoveryReady(facts);
    }

    #readBackgroundNotice(setup: AiSetupState): string | null {
        const downloadTasks = new Set(setup.models.flatMap((model) => (model.downloadTaskId === null ? [] : [model.downloadTaskId])));
        const installTasks = new Set(setup.engine.backends.flatMap((backend) => (backend.taskId === null ? [] : [backend.taskId])));
        const operations = requireTaskOperationsApi().getOperations();
        const downloads = operations.filter((operation) => operation.type === MODEL_DOWNLOAD_OPERATION_TYPE && downloadTasks.has(operation.id)).length;
        const installs = operations.filter((operation) => operation.type === BACKEND_INSTALL_OPERATION_TYPE && installTasks.has(operation.id)).length;
        if (downloads > 0 && installs > 0) return i18n.t('wizard.aiSetup.background.both');
        if (downloads > 0) return i18n.plural('wizard.aiSetup.background.downloads', downloads, { count: downloads });
        if (installs > 0) return i18n.plural('wizard.aiSetup.background.installations', installs, { count: installs });
        return null;
    }
}

export { AiSetupFlowController };
export type { AiSetupFlowControllerHost };
