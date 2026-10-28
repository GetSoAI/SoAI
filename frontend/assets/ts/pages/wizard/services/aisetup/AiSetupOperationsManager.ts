/* SoAI - Wizard AI setup installation and download operations [frontend/assets/ts/pages/wizard/services/aisetup/AiSetupOperationsManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { isLifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { i18n } from '@core/i18n/index.ts';
import { modelActions } from '@core/modelactions/public.ts';
import { normalizeOperationError } from '@core/operationErrorNotifier.ts';
import { taskProgressPayloadToOperationProgress } from '@core/operationprogress/taskProgressAdapter.ts';
import { MODELS } from '@core/realtime/streammanager/resources/ids.ts';
import type { AiSetupOperationsManagerHost } from '@pages/wizard/services/aisetup/contracts.ts';
import type { AiSetupModel } from '@core/storage/aisetup/aiSetupTypes.ts';
import { AiSetupTaskLifecycleController } from '@pages/wizard/services/aisetup/AiSetupTaskLifecycleController.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { WEBSOCKET_MESSAGE_TYPES } from '@core/websocketEvents.ts';
import { requireCatalogStore } from '@features/catalog/public.ts';
import { findActiveModelDownloadOperation, MODEL_DOWNLOAD_OPERATION_TYPE, runModelDownload } from '@features/models/public.ts';
import { createBackendStreamPorts, executeBackendOperation, type BackendOperationHost } from '@features/plugins/public.ts';
import { findItemModel, readAiSetupDownloadRequest } from '@pages/wizard/services/aisetup/catalog/mappers.ts';
import { AiSetupDiscoveryWatchController } from '@pages/wizard/services/aisetup/AiSetupDiscoveryWatchController.ts';
import { readEngineName, resolveItemEngine, isEngineInstalled } from '@pages/wizard/services/aisetup/facts/service.ts';
import { backendRowKey, readBackendRowPlugin, resolveEngineState, readDownloadResult, type SettledTaskResult, type TaskObservation } from '@pages/wizard/services/aisetup/progress/mappers.ts';
import { isDownloadCommitted, withBackendRepaired, withBackendTask, withCompletedLocalDownload, withItemExcluded, withModelTask } from '@pages/wizard/services/aisetup/state.ts';

const BACKEND_INSTALL_OPERATION_TYPE = 'backend-install';

class AiSetupOperationsManager {
    readonly #host: AiSetupOperationsManagerHost;
    readonly #observations = new Map<string, TaskObservation>();
    readonly #attempts = new AiSetupTaskLifecycleController();
    readonly #inFlight = new Set<string>();
    readonly #discovery: AiSetupDiscoveryWatchController;
    #disposed = false;

    constructor(host: AiSetupOperationsManagerHost) {
        this.#host = host;
        this.#discovery = new AiSetupDiscoveryWatchController(
            () => this.#host.onChange(),
            async () => {
                await this.#host.streaming.runtime().resources.refresh(MODELS, { allowDiscovery: true });
            }
        );
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
        this.#attempts.dispose();
    }

    reconcile(): void {
        const setup = this.#host.getSetup();
        for (const key of this.#inFlight) {
            if (readBackendRowPlugin(key) !== null || setup.models.some((item) => item.itemId === key && !item.excluded)) continue;
            this.#cancelInBackground(key);
        }
        for (const backend of setup.engine.backends) {
            if (!backend.excluded && backend.taskId !== null && !this.#observations.has(backendRowKey(backend.pluginName))) this.#attachInstall(backend.pluginName, backend.taskId);
        }
        const models = this.#host.getModels();
        for (const item of setup.models) {
            if (item.excluded && item.source === 'local' && item.downloadTaskId !== null && !this.#observations.has(item.itemId)) {
                this.#attachDownload(item, item.downloadTaskId);
                this.#cancelInBackground(item.itemId);
            }
            if (item.excluded || item.source !== 'local' || findItemModel(models, item) !== null) {
                this.#discovery.clear(item.itemId);
                continue;
            }
            if (item.modelId !== null) this.#discovery.arm(item.itemId);
            if (item.downloadTaskId !== null && !this.#observations.has(item.itemId)) this.#attachDownload(item, item.downloadTaskId);
        }
        if (isDownloadCommitted(setup)) this.startPendingDownloads();
    }

    startPendingDownloads(): void {
        const setup = this.#host.getSetup();
        const local = setup.models.filter((item) => item.source === 'local' && !item.excluded);
        if (local.length !== 1 || [...this.#inFlight].some((key) => readBackendRowPlugin(key) === null)) return;
        if (setup.models.some((item) => item.source === 'local' && item.excluded && (item.modelId !== null || this.#observations.get(item.itemId)?.status === 'succeeded'))) return;
        const models = this.#host.getModels();
        const engineContext = { setup, facts: this.#host.getFacts(), observations: this.#observations };
        for (const item of setup.models) {
            if (item.itemId !== setup.committedLocalItemId || item.excluded || item.source !== 'local' || item.modelId !== null || item.downloadTaskId !== null || this.#observations.has(item.itemId) || findItemModel(models, item) !== null) continue;
            if (resolveEngineState(engineContext, item.pluginName) === 'ready') this.#startDownload(item);
        }
    }

    startInstall(pluginName: string, variantId: string, commandType: 'plugin_backend_install' | 'plugin_backend_update' = WEBSOCKET_MESSAGE_TYPES.PLUGIN_BACKEND_INSTALL): void {
        const key = backendRowKey(pluginName);
        if (this.#inFlight.has(key)) return;
        const plugin = requireCatalogStore().getPlugin(pluginName);
        if (plugin === null) {
            this.#observe(key, { status: 'failed', insufficientDiskSpace: false });
            return;
        }
        this.#inFlight.add(key);
        this.#attempts.begin(key);
        this.#observe(key, { status: 'running', taskId: null, progress: null });
        void executeBackendOperation(this.#createBackendHost(key), plugin, {
            commandType,
            backendVariantId: variantId,
            operationMeta: { type: commandType === WEBSOCKET_MESSAGE_TYPES.PLUGIN_BACKEND_UPDATE ? 'backend-update' : BACKEND_INSTALL_OPERATION_TYPE },
            loadingMessage: i18n.t('plugins.loading.installingBackend'),
            failMessage: i18n.t('plugins.notifications.backendInstallFailed'),
            onStarted: (stream) => this.#attempts.attach(key, stream),
            onAccepted: (taskId) => {
                this.#host.updateSetup((setup) => withBackendTask(setup, pluginName, variantId, taskId));
                const observation = this.#observations.get(key);
                this.#observe(key, observation?.status === 'cancelling' ? { status: 'cancelling', taskId } : { status: 'running', taskId, progress: null });
            }
        })
            .then((outcome) => {
                if (outcome.status === 'succeeded' && commandType === WEBSOCKET_MESSAGE_TYPES.PLUGIN_BACKEND_UPDATE) this.#host.updateSetup((setup) => withBackendRepaired(setup, pluginName));
                this.#inFlight.delete(key);
                this.#settleInstall(pluginName, outcome.status === 'succeeded' ? 'succeeded' : outcome.status === 'detached' ? 'detached' : outcome.status === 'cancelled' ? 'cancelled' : 'failed');
            })
            .catch((error) => this.#reportSettlementFailure(key, error));
    }

    retryInstall(pluginName: string): void {
        const backend = this.#host.getSetup().engine.backends.find((entry) => entry.pluginName === pluginName) ?? null;
        const facts = this.#host.getFacts();
        const engine = facts === null ? null : resolveItemEngine(facts, pluginName);
        const variantId = backend?.variantId ?? (engine?.status === 'install' ? engine.variantId : null);
        if (variantId === null) return;
        this.#observations.delete(backendRowKey(pluginName));
        this.startInstall(pluginName, variantId, facts !== null && isEngineInstalled(facts, pluginName) ? WEBSOCKET_MESSAGE_TYPES.PLUGIN_BACKEND_UPDATE : WEBSOCKET_MESSAGE_TYPES.PLUGIN_BACKEND_INSTALL);
    }

    retryDownload(itemId: string): void {
        const item = this.#host.getSetup().models.find((entry) => entry.itemId === itemId) ?? null;
        if (item === null || item.excluded || item.source !== 'local' || this.#inFlight.has(itemId)) return;
        this.#observations.delete(itemId);
        this.#host.updateSetup((setup) => withModelTask(setup, itemId, null));
        this.#startDownload(item);
    }

    async cancel(rowKey: string): Promise<void> {
        const observation = this.#observations.get(rowKey);
        if (observation === undefined) {
            this.#host.updateSetup((setup) => withItemExcluded(setup, rowKey));
            this.#host.onChange();
            return;
        }
        if (observation.status !== 'running' && observation.status !== 'checking') return;
        this.#observe(rowKey, { status: 'cancelling', taskId: observation.taskId });
        try {
            await this.#attempts.cancel(rowKey);
        } catch (error) {
            if (this.#observations.get(rowKey)?.status === 'cancelling') this.#observe(rowKey, observation);
            throw error;
        }
    }

    #cancelInBackground(key: string): void {
        void this.cancel(key).catch((error) => this.#host.notify(normalizeOperationError(ensureError(error))?.message ?? i18n.t('common.cancellation.failed'), 'warning'));
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

    #attachInstall(pluginName: string, taskId: string): void {
        const key = backendRowKey(pluginName);
        if (this.#inFlight.has(key)) return;
        this.#inFlight.add(key);
        this.#observe(key, { status: 'checking', taskId });
        this.#attempts.begin(key);
        const stream = this.#host.streaming.runtime().tasks.trackAcceptedTask(taskId, { handlers: this.#host.streaming.handlers({ onProgress: (data) => this.#updateProgress(key, data) }), operation: { type: BACKEND_INSTALL_OPERATION_TYPE, pluginName } });
        this.#attempts.attach(key, stream);
        void this.#attempts
            .settle(stream, BACKEND_INSTALL_OPERATION_TYPE, i18n.t('plugins.notifications.backendInstallFailed'), this.#host.streaming.pageTracker)
            .then((result) => {
                this.#inFlight.delete(key);
                this.#settleInstall(pluginName, result === 'failed_disk' ? 'failed' : result);
            })
            .catch((error) => this.#reportSettlementFailure(key, error));
    }

    #settleInstall(pluginName: string, result: 'succeeded' | 'failed' | 'cancelled' | 'detached'): void {
        if (this.#disposed || result === 'detached') return;
        const key = backendRowKey(pluginName);
        this.#attempts.finish(key);
        if (result === 'cancelled') {
            this.#observe(key, { status: 'cancelled' });
            return;
        }
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
            .catch((error) => {
                const runtimeError = ensureError(error);
                if (!this.#disposed && !isAbortError(runtimeError) && !isLifecycleCancellationError(runtimeError)) errorHandler.warn('WizardAiSetup', `Engine facts refresh after installing ${pluginName} failed`, runtimeError);
            });
    }

    #startDownload(item: AiSetupModel): void {
        const request = readAiSetupDownloadRequest(this.#host.getSetup(), item);
        if (request === null || this.#inFlight.has(item.itemId)) return;
        const itemId = item.itemId;
        this.#inFlight.add(itemId);
        const attempt = this.#attempts.begin(itemId);
        this.#observe(itemId, { status: 'running', taskId: null, progress: null });
        void runModelDownload({
            request,
            signal: attempt.controller.signal,
            startDownload: (downloadRequest, options) => modelActions.startDownload(downloadRequest, options),
            handlers: this.#host.streaming.handlers({ onProgress: (data) => this.#updateProgress(itemId, data) }),
            tracker: this.#host.streaming.pageTracker,
            failMessage: i18n.t('models.notifications.downloadFailed'),
            onStarted: (stream) => {
                this.#attempts.attach(itemId, stream, (taskId) => this.#host.updateSetup((setup) => withModelTask(setup, itemId, taskId, true)));
            }
        })
            .then(async (outcome) => {
                this.#inFlight.delete(itemId);
                this.#attempts.finish(itemId);
                if (outcome.status === 'rejected') {
                    this.#handleRejectedDownload(item, outcome.reason, findActiveModelDownloadOperation(request)?.id ?? null);
                    return;
                }
                if (outcome.status === 'failed' && (await this.#attempts.recoverDownload(outcome.error, itemId, this.#host, this.#attachRecoveredDownload, attempt.controller.signal.aborted))) return;
                this.#settleDownload(itemId, readDownloadResult(outcome));
            })
            .catch((error) => this.#reportSettlementFailure(itemId, error));
    }

    readonly #attachRecoveredDownload = (item: AiSetupModel, taskId: string, cancel: boolean): void => {
        this.#attachDownload(item, taskId);
        if (cancel) this.#cancelInBackground(item.itemId);
    };

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
        this.#attempts.finish(key);
        errorHandler.error('WizardAiSetup', `AI setup operation ${key} could not be settled`, ensureError(error));
        this.#observe(key, { status: 'failed', insufficientDiskSpace: false });
    }

    #attachDownload(item: AiSetupModel, taskId: string): void {
        const itemId = item.itemId;
        if (this.#inFlight.has(itemId)) return;
        this.#inFlight.add(itemId);
        this.#observe(itemId, { status: 'checking', taskId });
        this.#attempts.begin(itemId);
        const stream = this.#host.streaming.runtime().tasks.trackAcceptedTask(taskId, { handlers: this.#host.streaming.handlers({ onProgress: (data) => this.#updateProgress(itemId, data) }), operation: { type: MODEL_DOWNLOAD_OPERATION_TYPE, pluginName: item.pluginName } });
        this.#attempts.attach(itemId, stream);
        void this.#attempts
            .settle(stream, MODEL_DOWNLOAD_OPERATION_TYPE, i18n.t('models.notifications.downloadFailed'), this.#host.streaming.pageTracker)
            .then((result) => {
                this.#inFlight.delete(itemId);
                this.#settleDownload(itemId, result);
            })
            .catch((error) => this.#reportSettlementFailure(itemId, error));
    }

    #settleDownload(itemId: string, result: SettledTaskResult): void {
        this.#attempts.finish(itemId);
        if (this.#disposed || result === 'detached') return;
        if (result === 'cancelled') {
            this.#observe(itemId, { status: 'cancelled' });
            this.startPendingDownloads();
            return;
        }
        if (result !== 'succeeded') {
            this.#observe(itemId, { status: 'failed', insufficientDiskSpace: result === 'failed_disk' });
            this.startPendingDownloads();
            return;
        }
        this.#host.updateSetup((setup) => withCompletedLocalDownload(setup, itemId));
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

export { AiSetupOperationsManager, BACKEND_INSTALL_OPERATION_TYPE };
export type { AiSetupOperationsManagerHost };
