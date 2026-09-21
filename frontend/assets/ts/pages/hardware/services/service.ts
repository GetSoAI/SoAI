/* SoAI - Hardware page services service [frontend/assets/ts/pages/hardware/services/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeGpuOperationResponse } from '@core/api/contracts/hardwareContracts.ts';
import { serializeGpuDeviceSettingsRequest, serializeGpuRunIdentifierRequest, serializeGpuSlotApplyRequest, serializeGpuSlotStoreSnapshotRequest, serializeGpuSoAIBenchDeviceStartRequest, serializeKillProcessRequest } from '@core/api/contracts/hardwareRequestContracts.ts';
import type { ElementOptions } from '@core/dom/dom.ts';
import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import { renderCachedContent } from '@core/dom/renderCache.ts';
import { HARDWARE_GPU_SOAIBENCH_RUNS } from '@core/realtime/streammanager/resources/ids.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { requestWebSocketSnapshotRecord } from '@core/websocketclient/snapshotPayload.ts';
import { ExportPreviewModal } from '@features/exportpreview/public.ts';
import { SoAIBenchHistoryModal, SoAIBenchPublicationFlow, SoAIBenchRunModal, SystemInfoModal } from '@features/hardware/public.ts';
import { createHardwareProcessController } from '@pages/hardware/adapters/adapters.ts';
import type { HardwarePageDependencies } from '@pages/hardware/contracts/hardwarePageSupport.ts';
import { normalizeHardwareNotificationType } from '@pages/hardware/controllers/effects.ts';
import { GpuControlManager } from '@pages/hardware/controllers/gpucontrol/GpuControlManager.ts';
import type { ApiService, GpuControlManagerDependencies, StreamRefresher } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';
import { createHardwareGpuApi } from '@pages/hardware/controllers/hardwareControllerFactories.ts';
import { createHardwareCardRendererHosts, createSoAIBenchHistoryModalHost, createSystemInfoModalHost } from '@pages/hardware/controllers/hardwareHostFactories.ts';
import { persistHardwarePageControls, readHardwareProcessSortState } from '@pages/hardware/controllers/page/hardwarePageControlsController.ts';
import { NetworkCardRenderer } from '@pages/hardware/rendering/cards/NetworkCardRenderer.ts';
import { StorageCardRenderer } from '@pages/hardware/rendering/cards/StorageCardRenderer.ts';
import type { HardwareGpuControllerDependencies, HardwareProcessControllerDependencies, HardwareUiDependencies } from '@pages/hardware/services/contracts.ts';
import { ProcessTableManager } from '@pages/hardware/widgets/processes/service.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';

const resolveHardwareStreamManager = async (streaming: HardwareGpuControllerDependencies['owners']['streaming'], options: { signal?: AbortSignal | null | undefined } = {}): Promise<StreamRefresher> => {
    throwIfAborted(options.signal ?? undefined);
    return streaming.runtime().resources;
};

const createHardwareGpuController = (dependencies: HardwareGpuControllerDependencies, security: HardwarePageDependencies['security']): GpuControlManager => {
    const { owners } = dependencies;
    const gpuApi: ApiService = createHardwareGpuApi({
        updateGpuDevice: async (deviceId, payload) => {
            return decodeGpuOperationResponse(await requestWebSocketSnapshotRecord('hardware.gpu.settings.update', serializeGpuDeviceSettingsRequest(deviceId, payload)));
        },
        startGpuSoAIBench: async (deviceId, payload) => {
            return decodeGpuOperationResponse(await requestWebSocketSnapshotRecord('hardware.gpu.soaibench.start', serializeGpuSoAIBenchDeviceStartRequest(deviceId, payload)));
        },
        stopGpuSoAIBench: async (runId) => {
            return decodeGpuOperationResponse(await requestWebSocketSnapshotRecord('hardware.gpu.soaibench.stop', serializeGpuRunIdentifierRequest(runId)));
        },
        runsGpuSoAIBench: async (payload) => {
            return decodeGpuOperationResponse(await requestWebSocketSnapshotRecord('hardware.gpu.soaibench.runs', { limit: payload.limit }));
        },
        applyGpuSlot: async (deviceId, slot, boot) => {
            return decodeGpuOperationResponse(await requestWebSocketSnapshotRecord('hardware.gpu.slots.apply', serializeGpuSlotApplyRequest(deviceId, slot, boot)));
        },
        storeGpuSlot: async (deviceId, slot, payload) => {
            return decodeGpuOperationResponse(await requestWebSocketSnapshotRecord('hardware.gpu.slots.store', serializeGpuSlotStoreSnapshotRequest(deviceId, slot, payload)));
        }
    });
    const gpuControlDependencies: GpuControlManagerDependencies = {
        dom: owners.dom,
        api: gpuApi,
        chartOhlc: dependencies.chartRuntime.getOhlc(),
        runPageTask: async (taskId, taskFunctionValue, options) => {
            await owners.streaming.runTask(taskId, taskFunctionValue, options);
        },
        showNotification: (message: string, type: string) => owners.feedback.show(message, normalizeHardwareNotificationType(type)),
        showSoAIBenchHistory: (request) => dependencies.historyModal.open(request),
        showSoAIBenchRun: (request) => dependencies.runModal.open(request),
        handleSoAIBenchRunsUpdate: (value) => dependencies.runModal.handleRunsUpdate(isJsonObject(value) ? value : null),
        resolveStreamManager: () => resolveHardwareStreamManager(owners.streaming),
        getIconSync: (iconName, options) => owners.services.getIconSync(iconName, options)
    };
    return new GpuControlManager(gpuControlDependencies, { security });
};

const composeHardwareProcessController = (dependencies: HardwareProcessControllerDependencies): ProcessTableManager => {
    const { owners } = dependencies;
    const processController = createHardwareProcessController({
        optionalHTMLElement: (selector: string, parent?: Element | null) => (parent ? owners.pageDom.optionalHTMLElement(selector, parent) : owners.pageDom.optionalHTMLElement(selector)),
        updateText: (element: Element, text: string) => owners.pageDom.updateText(element, text),
        getIconSync: (iconName: IconName, options?: IconOptions) => owners.services.getIconSync(iconName, options),
        runWithBoundary: (boundaryKey: string, functionValue: () => Promise<void>) => owners.pageLifecycle.run(boundaryKey, functionValue),
        showNotification: (message: string, type: string, duration?: number) => owners.feedback.show(message, normalizeHardwareNotificationType(type), duration),
        killProcess: async (pid: string, options: { signal: number; useSudo: boolean; throwOnError?: boolean; notifyOnError?: boolean }) => {
            return requestWebSocketSnapshotRecord('hardware.process.kill', serializeKillProcessRequest(Number(pid), options.signal, options.useSudo));
        },
        getLastSnapshot: () => dependencies.state.lastSnapshot,
        onSortChanged: (state) => persistHardwarePageControls(owners.storage, dependencies.state, state)
    });
    const processSort = readHardwareProcessSortState(owners.storage);
    processController.sortColumn = processSort.column;
    processController.sortDirection = processSort.direction;
    return processController;
};

const initializeHardwareUi = (
    dependencies: HardwareUiDependencies
): {
    networkCardRenderer: NetworkCardRenderer;
    storageCardRenderer: StorageCardRenderer;
    systemInfoModal: SystemInfoModal;
    exportPreviewModal: ExportPreviewModal;
    soaibenchHistoryModal: SoAIBenchHistoryModal;
    soaibenchRunModal: SoAIBenchRunModal;
} => {
    const { owners } = dependencies;
    const cardRendererHosts = createHardwareCardRendererHosts({
        createElement: (tag: string, attrs: ElementOptions, child?: string | Node) => owners.pageElements.createElement(tag, attrs, child),
        updateText: (element: Element, text: string) => owners.pageDom.updateText(element, text),
        optionalUI: (selector: string) => owners.pageDom.optional(selector),
        renderCachedContent: (container: Element, key: string, factory: () => Element | DocumentFragment) => renderCachedContent(container, key, factory)
    });
    const networkCardRenderer = new NetworkCardRenderer({ host: cardRendererHosts.network });
    const storageCardRenderer = new StorageCardRenderer({ host: cardRendererHosts.storage });
    const systemInfoModal = new SystemInfoModal({
        host: createSystemInfoModalHost({
            modals: owners.services.modals,
            domHasClass: (element: Element, className: string): boolean => owners.dom.hasClass(element, className),
            requireHTMLElement: (selector: string | Element, context?: Element): HTMLElement => owners.pageDom.requireHTMLElement(selector, context),
            runWithBoundary: <T>(boundaryKey: string, functionValue: () => Promise<T>): Promise<T> => owners.pageLifecycle.run(boundaryKey, functionValue),
            hasClipboardSupport: (): boolean => owners.services.hasClipboardSupport(),
            copyToClipboard: (value: string, options?: { notify(message: string, type: NotificationType): void }): Promise<void> => owners.services.copyToClipboard(value, options),
            updateProperty: (target: Element, property: string, value: DomPropertyValue): void => owners.pageDom.updateProperty(target, property, value),
            addClassName: (target: Element, className: string): void => owners.pageDom.addClass(target, className),
            removeClassName: (target: Element, className: string): void => owners.pageDom.removeClass(target, className),
            updateText: (target: Element, text: string): void => owners.pageDom.updateText(target, text),
            setDataAttribute: (target: Element, name: string, value: string | null): void => owners.pageDom.setDataAttribute(target, name, value),
            getDataAttribute: (target: Element, name: string): string | null => owners.pageDom.getDataAttribute(target, name),
            showNotification: (message: string, type: NotificationType, duration?: number): void => owners.feedback.show(message, type, duration)
        })
    });
    const exportPreviewModal = new ExportPreviewModal({
        host: {
            modals: owners.services.modals,
            requireHTMLElement: (selector: string | Element, context?: Element): HTMLElement => owners.pageDom.requireHTMLElement(selector, context),
            runWithBoundary: <T>(boundaryKey: string, functionValue: () => Promise<T>): Promise<T> => owners.pageLifecycle.run(boundaryKey, functionValue),
            addClassName: (target: Element, className: string): void => owners.pageDom.addClass(target, className),
            removeClassName: (target: Element, className: string): void => owners.pageDom.removeClass(target, className),
            updateText: (target: Element, text: string): void => owners.pageDom.updateText(target, text),
            showNotification: (message, type): void => owners.feedback.show(message, type)
        }
    });
    const publicationFlow = new SoAIBenchPublicationFlow({
        preview: (runId) => owners.api.hardware.gpuSoAIBench.preview(runId),
        showResult: async (receipt, message) => {
            await requireDialogsService().showExternalLinkModal({
                url: receipt.publicUrl,
                title: i18n.t('common.success'),
                message,
                cancelText: i18n.t('common.close'),
                confirmText: i18n.t('common.ok')
            });
        },
        publish: (runId) => owners.api.hardware.gpuSoAIBench.publish(runId),
        confirm: (options) => requireDialogsService().showConfirmation(options),
        showNotification: (message, type) => owners.feedback.show(message, type)
    });
    const soaibenchHistoryModal = new SoAIBenchHistoryModal({
        deleteLocalRun: async (runId) => {
            await owners.api.hardware.gpuSoAIBench.deleteLocal(runId);
        },
        publishRun: (run, setDisabled) => publicationFlow.publish({ runId: run.runId, publicationEligible: run.publicationEligible, overallScore: run.telemetry.overallScore, measuredPasses: 5 }, setDisabled),
        host: createSoAIBenchHistoryModalHost({
            modals: owners.services.modals,
            downloadHistoryCsv: (deviceId: string): Promise<Response> => owners.api.hardware.gpuSoAIBench.exportHistory(deviceId),
            requireHTMLElement: (selector: string | Element, context?: Element): HTMLElement => owners.pageDom.requireHTMLElement(selector, context),
            setHTML: (target, html): void => owners.dom.setHTML(target, html, { escape: false }),
            runWithBoundary: <T>(boundaryKey: string, functionValue: () => Promise<T>): Promise<T> => owners.pageLifecycle.run(boundaryKey, functionValue),
            hasClipboardSupport: (): boolean => owners.services.hasClipboardSupport(),
            copyToClipboard: (value: string, options?: { notify(message: string, type: NotificationType): void }): Promise<void> => owners.services.copyToClipboard(value, options),
            addClassName: (target: Element, className: string): void => owners.pageDom.addClass(target, className),
            removeClassName: (target: Element, className: string): void => owners.pageDom.removeClass(target, className),
            updateText: (target: Element, text: string): void => owners.pageDom.updateText(target, text),
            showNotification: (message: string, type: NotificationType, duration?: number): void => owners.feedback.show(message, type, duration),
            getIconSync: (iconName, options) => owners.services.getIconSync(iconName, options)
        })
    });
    const soaibenchRunModal = new SoAIBenchRunModal({
        publishRun: (run, setDisabled) => publicationFlow.publish({ runId: run.runId, publicationEligible: run.publicationEligible, overallScore: run.metrics.overallScore, measuredPasses: run.metrics.measuredPassesCompleted }, setDisabled),
        host: {
            modals: owners.services.modals,
            requireHTMLElement: (selector: string | Element, context?: Element): HTMLElement => owners.pageDom.requireHTMLElement(selector, context),
            setHTML: (target, html): void => owners.dom.setHTML(target, html, { escape: false }),
            runWithBoundary: <T>(boundaryKey: string, functionValue: () => Promise<T>): Promise<T> => owners.pageLifecycle.run(boundaryKey, functionValue),
            addClassName: (target: Element, className: string): void => owners.pageDom.addClass(target, className),
            removeClassName: (target: Element, className: string): void => owners.pageDom.removeClass(target, className),
            updateText: (target: Element, text: string): void => owners.pageDom.updateText(target, text),
            showNotification: (message: string, type: NotificationType, duration?: number): void => owners.feedback.show(message, type, duration),
            refreshSoAIBenchRuns: async (): Promise<JsonObject | null> => {
                const streamManager = await resolveHardwareStreamManager(owners.streaming);
                const runs = await streamManager.refresh(HARDWARE_GPU_SOAIBENCH_RUNS);
                return isJsonObject(runs) ? runs : null;
            },
            hasClipboardSupport: (): boolean => owners.services.hasClipboardSupport(),
            copyToClipboard: (value: string, options?: { notify(message: string, type: NotificationType): void }): Promise<void> => owners.services.copyToClipboard(value, options),
            renderGpuControls: (options?: { only?: string[] | null }): void => dependencies.renderGpuControls(options),
            showSoAIBenchHistory: (request): Promise<void> => dependencies.showSoAIBenchHistory(request)
        }
    });
    return { networkCardRenderer, storageCardRenderer, systemInfoModal, exportPreviewModal, soaibenchHistoryModal, soaibenchRunModal };
};

export { createHardwareGpuController, composeHardwareProcessController, initializeHardwareUi };
