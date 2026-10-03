/* SoAI - Wizard AI setup installation and download operations [frontend/assets/ts/pages/wizard/services/aisetup/AiSetupOperationsManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { modelActions } from '@core/modelactions/public.ts';
import { normalizeOperationError } from '@core/operationErrorNotifier.ts';
import { taskProgressPayloadToOperationProgress } from '@core/operationprogress/taskProgressAdapter.ts';
import { MODELS } from '@core/realtime/streammanager/resources/ids.ts';
import type { PageStreamingContract } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { AiSetupModel, AiSetupState } from '@core/storage/aisetup/aiSetupTypes.ts';
import { settleTrackedTaskStream } from '@core/tasks/trackedTaskStream.ts';
import { requireTaskOperationsApi } from '@core/tasks/serviceAccess.ts';
import type { StreamActionHandle } from '@core/routing/pages/pagetypes/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { WEBSOCKET_MESSAGE_TYPES } from '@core/websocketEvents.ts';
import { requireCatalogStore } from '@features/catalog/public.ts';
import { findActiveModelDownloadOperation, MODEL_DOWNLOAD_OPERATION_TYPE, runModelDownload, type ModelDownloadOutcome } from '@features/models/public.ts';
import { createBackendStreamPorts, executeBackendOperation, type BackendOperationHost } from '@features/plugins/public.ts';
import { findItemModel } from '@pages/wizard/services/aisetup/catalog/mappers.ts';
import { AiSetupDiscoveryWatchController } from '@pages/wizard/services/aisetup/AiSetupDiscoveryWatchController.ts';
import { readEngineName, type AiSetupFacts } from '@pages/wizard/services/aisetup/facts/service.ts';
import { backendRowKey, resolveEngineState, type TaskObservation } from '@pages/wizard/services/aisetup/progress/mappers.ts';
import { withBackendTask, withModelTask } from '@pages/wizard/services/aisetup/state.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import { findModelCatalogEntry } from '@pages/wizard/services/aisetup/catalog/constants.ts';

const BACKEND_INSTALL_OPERATION_TYPE = 'backend-install';

interface AiSetupOperationsManagerHost {
    streaming: PageStreamingContract;
    getSetup(): AiSetupState;
    updateSetup(update: (setup: AiSetupState) => AiSetupState): void;
    getFacts(): AiSetupFacts | null;
    getModels(): readonly ModelData[];
    onEngineInstalled(pluginName: string): Promise<void>;
    onChange(): void;
    notify(message: string, type: NotificationType): void;
}

class AiSetupOperationsManager {
    readonly #host: AiSetupOperationsManagerHost;
    readonly #observations = new Map<string, TaskObservation>();
    readonly #inFlight = new Set<string>();
    readonly #discovery: AiSetupDiscoveryWatchController;
    #disposed = false;

    constructor(host: AiSetupOperationsManagerHost) {
        this.#host = host;
        this.#discovery = new AiSetupDiscoveryWatchController(() => this.#host.onChange());
    }

    get observations(): ReadonlyMap<string, TaskObservation> {
        return this.#observations;
    }

    get stalledDiscovery(): ReadonlySet<string> {
        return this.#discovery.stalled;
    }

    dispose(): void {
        this.#disposed = true;
        this.#discovery.dispose();
    }

    reconcile(): void {
        const setup = this.#host.getSetup();
        for (const backend of setup.engine.backends) {
            if (!backend.excluded && backend.taskId !== null && !this.#observations.has(backendRowKey(backend.pluginName))) this.#attachInstall(backend.pluginName, backend.taskId);
        }
        const models = this.#host.getModels();
        for (const item of setup.models) {
            if (item.excluded || item.source !== 'local' || findItemModel(models, item) !== null) {
                this.#discovery.clear(item.itemId);
                continue;
            }
            if (item.downloadTaskId !== null && !this.#observations.has(item.itemId)) this.#attachDownload(item, item.downloadTaskId);
        }
        if (isDownloadCommitted(setup)) this.startPendingDownloads();
    }

    startPendingDownloads(): void {
        const setup = this.#host.getSetup();
        const models = this.#host.getModels();
        const engineContext = { setup, facts: this.#host.getFacts(), observations: this.#observations };
        for (const item of setup.models) {
            if (item.excluded || item.source !== 'local' || item.downloadTaskId !== null || this.#observations.has(item.itemId) || findItemModel(models, item) !== null) continue;
            if (resolveEngineState(engineContext, item.pluginName) === 'ready') this.#startDownload(item);
        }
    }

    startInstall(pluginName: string, variantId: string): void {
        const key = backendRowKey(pluginName);
        if (this.#inFlight.has(key)) return;
        const plugin = requireCatalogStore().getPlugin(pluginName);
        if (plugin === null) {
            this.#observe(key, { status: 'failed', insufficientDiskSpace: false });
            return;
        }
        this.#inFlight.add(key);
        this.#observe(key, { status: 'running', taskId: null, progress: null });
        void executeBackendOperation(this.#createBackendHost(key), plugin, {
            commandType: WEBSOCKET_MESSAGE_TYPES.PLUGIN_BACKEND_INSTALL,
            backendVariantId: variantId,
            operationMeta: { type: BACKEND_INSTALL_OPERATION_TYPE },
            loadingMessage: i18n.t('plugins.loading.installingBackend'),
            failMessage: i18n.t('plugins.notifications.backendInstallFailed'),
            onAccepted: (taskId) => {
                this.#host.updateSetup((setup) => withBackendTask(setup, pluginName, variantId, taskId));
                this.#observe(key, { status: 'running', taskId, progress: null });
            }
        })
            .then((outcome) => {
                this.#inFlight.delete(key);
                this.#settleInstall(pluginName, outcome.status === 'succeeded' ? 'succeeded' : outcome.status === 'detached' ? 'detached' : 'failed');
            })
            .catch((error) => this.#reportSettlementFailure(key, error));
    }

    retryInstall(pluginName: string): void {
        const backend = this.#host.getSetup().engine.backends.find((entry) => entry.pluginName === pluginName) ?? null;
        const variantId = backend?.variantId ?? this.#resolveInstallVariant(pluginName);
        if (variantId === null) return;
        this.#observations.delete(backendRowKey(pluginName));
        this.startInstall(pluginName, variantId);
    }

    retryDownload(itemId: string): void {
        const item = this.#host.getSetup().models.find((entry) => entry.itemId === itemId) ?? null;
        if (item === null || item.source !== 'local' || this.#inFlight.has(itemId)) return;
        this.#observations.delete(itemId);
        this.#host.updateSetup((setup) => withModelTask(setup, itemId, null));
        this.#startDownload(item);
    }

    checkAgain(itemId: string): void {
        this.#discovery.restart(itemId);
        this.#host.onChange();
        void this.#host.streaming
            .runtime()
            .resources.refresh(MODELS, { allowDiscovery: true })
            .catch((error) => errorHandler.warn('WizardAiSetup', 'Model catalog refresh failed', ensureError(error)));
    }

    async cancel(rowKey: string): Promise<void> {
        const observation = this.#observations.get(rowKey);
        if (observation?.status !== 'running' || observation.taskId === null) return;
        await requireTaskOperationsApi().cancelOperationById(observation.taskId);
    }

    #createBackendHost(key: string): BackendOperationHost {
        const ports = createBackendStreamPorts(this.#host.streaming);
        return {
            ...ports,
            streams: this.#host.streaming.pageTracker,
            createStreamHandlers: () => this.#host.streaming.handlers({ onProgress: (data) => this.#updateProgress(key, data) }),
            beginOptimisticOperation: (operation) => requireCatalogStore().beginOptimisticOperation(operation),
            formatPluginName: (name) => readEngineName(this.#host.getFacts(), name),
            showNotification: (message, type) => this.#host.notify(message, type ?? 'info')
        };
    }

    #resolveInstallVariant(pluginName: string): string | null {
        const option = this.#host.getFacts()?.engineOptions.find((entry) => entry.pluginName === pluginName) ?? null;
        return option !== null && option.engine.status === 'install' ? option.engine.variantId : null;
    }

    #attachInstall(pluginName: string, taskId: string): void {
        const key = backendRowKey(pluginName);
        if (this.#inFlight.has(key)) return;
        this.#inFlight.add(key);
        this.#observe(key, { status: 'checking', taskId });
        const stream = this.#host.streaming.runtime().tasks.trackAcceptedTask(taskId, { handlers: this.#host.streaming.handlers({ onProgress: (data) => this.#updateProgress(key, data) }), operation: { type: BACKEND_INSTALL_OPERATION_TYPE, pluginName } });
        void this.#settleStream(stream, BACKEND_INSTALL_OPERATION_TYPE, i18n.t('plugins.notifications.backendInstallFailed'))
            .then((result) => {
                this.#inFlight.delete(key);
                this.#settleInstall(pluginName, result === 'failed_disk' ? 'failed' : result);
            })
            .catch((error) => this.#reportSettlementFailure(key, error));
    }

    #settleInstall(pluginName: string, result: 'succeeded' | 'failed' | 'detached'): void {
        if (this.#disposed || result === 'detached') return;
        const key = backendRowKey(pluginName);
        if (result === 'failed') {
            this.#observe(key, { status: 'failed', insufficientDiskSpace: false });
            return;
        }
        this.#observe(key, { status: 'succeeded' });
        void this.#host
            .onEngineInstalled(pluginName)
            .then(() => {
                if (this.#disposed) return;
                if (isDownloadCommitted(this.#host.getSetup())) this.startPendingDownloads();
                this.#host.onChange();
            })
            .catch((error) => errorHandler.warn('WizardAiSetup', `Engine facts refresh after installing ${pluginName} failed`, ensureError(error)));
    }

    #startDownload(item: AiSetupModel): void {
        if (item.repositoryId === null || item.artifactReference === null || this.#inFlight.has(item.itemId)) return;
        const itemId = item.itemId;
        const request = { plugin: item.pluginName, modelId: item.repositoryId, quantization: item.artifactReference, displayName: findModelCatalogEntry(item.catalogId)?.name ?? item.artifactName ?? item.artifactReference };
        this.#inFlight.add(itemId);
        this.#observe(itemId, { status: 'running', taskId: null, progress: null });
        void runModelDownload({
            request,
            startDownload: (downloadRequest, options) => modelActions.startDownload(downloadRequest, options),
            handlers: this.#host.streaming.handlers({ onProgress: (data) => this.#updateProgress(itemId, data) }),
            tracker: this.#host.streaming.pageTracker,
            failMessage: i18n.t('models.notifications.downloadFailed'),
            onStarted: (stream) => this.#recordDownloadTask(itemId, stream)
        })
            .then((outcome) => {
                this.#inFlight.delete(itemId);
                if (outcome.status === 'rejected') {
                    this.#handleRejectedDownload(item, outcome.reason, findActiveModelDownloadOperation(request)?.id ?? null);
                    return;
                }
                this.#settleDownload(itemId, readDownloadResult(outcome));
            })
            .catch((error) => this.#reportSettlementFailure(itemId, error));
    }

    #handleRejectedDownload(item: AiSetupModel, reason: 'max_concurrent' | 'already_downloading', existingTaskId: string | null): void {
        if (reason === 'already_downloading' && existingTaskId !== null) {
            this.#host.updateSetup((setup) => withModelTask(setup, item.itemId, existingTaskId));
            this.#attachDownload(item, existingTaskId);
            return;
        }
        if (reason === 'max_concurrent') this.#host.notify(i18n.t('models.notifications.maxConcurrentDownloads'), 'warning');
        this.#observe(item.itemId, reason === 'already_downloading' ? { status: 'checking', taskId: null } : { status: 'failed', insufficientDiskSpace: false });
    }

    #reportSettlementFailure(key: string, error: Error | JsonValue | null | undefined): void {
        this.#inFlight.delete(key);
        errorHandler.error('WizardAiSetup', `AI setup operation ${key} could not be settled`, ensureError(error));
        this.#observe(key, { status: 'failed', insufficientDiskSpace: false });
    }

    #recordDownloadTask(itemId: string, stream: StreamActionHandle): void {
        void stream.accepted
            ?.then((taskId) => {
                this.#host.updateSetup((setup) => withModelTask(setup, itemId, taskId));
                const observation = this.#observations.get(itemId);
                if (observation?.status === 'running') this.#observe(itemId, { ...observation, taskId });
            })
            .catch((error) => errorHandler.warn('WizardAiSetup', 'Model download acceptance was not confirmed', ensureError(error)));
    }

    #attachDownload(item: AiSetupModel, taskId: string): void {
        const itemId = item.itemId;
        if (this.#inFlight.has(itemId)) return;
        this.#inFlight.add(itemId);
        this.#observe(itemId, { status: 'checking', taskId });
        const stream = this.#host.streaming.runtime().tasks.trackAcceptedTask(taskId, { handlers: this.#host.streaming.handlers({ onProgress: (data) => this.#updateProgress(itemId, data) }), operation: { type: MODEL_DOWNLOAD_OPERATION_TYPE, pluginName: item.pluginName } });
        void this.#settleStream(stream, MODEL_DOWNLOAD_OPERATION_TYPE, i18n.t('models.notifications.downloadFailed'))
            .then((result) => {
                this.#inFlight.delete(itemId);
                this.#settleDownload(itemId, result);
            })
            .catch((error) => this.#reportSettlementFailure(itemId, error));
    }

    async #settleStream(stream: StreamActionHandle, keyPrefix: string, failMessage: string): Promise<SettledTaskResult> {
        try {
            const settled = await settleTrackedTaskStream({ tracker: this.#host.streaming.pageTracker, stream, keyPrefix, failMessage });
            if (settled.detached) return 'detached';
            return settled.cancelled ? 'failed' : 'succeeded';
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.warn('WizardAiSetup', `Tracked ${keyPrefix} task did not complete`, runtimeError);
            return normalizeOperationError(runtimeError)?.isInsufficientDiskSpace === true ? 'failed_disk' : 'failed';
        }
    }

    #settleDownload(itemId: string, result: SettledTaskResult): void {
        if (this.#disposed || result === 'detached') return;
        if (result !== 'succeeded') {
            this.#observe(itemId, { status: 'failed', insufficientDiskSpace: result === 'failed_disk' });
            return;
        }
        this.#observe(itemId, { status: 'succeeded' });
        this.#discovery.arm(itemId);
        void this.#host.streaming
            .runtime()
            .resources.refresh(MODELS, { allowDiscovery: true })
            .catch((error) => errorHandler.warn('WizardAiSetup', 'Model catalog refresh after download failed', ensureError(error)));
    }

    #updateProgress(key: string, data: JsonValue | null): void {
        const observation = this.#observations.get(key);
        if (observation?.status !== 'running' && observation?.status !== 'checking') return;
        this.#observe(key, { status: 'running', taskId: observation.taskId, progress: taskProgressPayloadToOperationProgress(data) });
    }

    #observe(key: string, observation: TaskObservation): void {
        if (this.#disposed) return;
        this.#observations.set(key, observation);
        this.#host.onChange();
    }
}

type SettledTaskResult = 'succeeded' | 'failed' | 'failed_disk' | 'detached';

const readDownloadResult = (outcome: Exclude<ModelDownloadOutcome, { status: 'rejected' }>): SettledTaskResult => {
    if (outcome.status === 'finished') return 'succeeded';
    if (outcome.status === 'detached') return 'detached';
    return outcome.status === 'failed' && outcome.insufficientDiskSpace ? 'failed_disk' : 'failed';
};

const isDownloadCommitted = (setup: AiSetupState): boolean => setup.step === 'ai_progress';

export { AiSetupOperationsManager, BACKEND_INSTALL_OPERATION_TYPE, isDownloadCommitted };
export type { AiSetupOperationsManagerHost };
