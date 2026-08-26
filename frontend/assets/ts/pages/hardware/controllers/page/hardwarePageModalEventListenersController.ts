/* SoAI - Hardware page modal event listeners controller [frontend/assets/ts/pages/hardware/controllers/page/hardwarePageModalEventListenersController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { shouldPreventDefaultForActionElement } from '@core/dom/dataAction.ts';
import { bindDataActionListener } from '@core/dom/dataActionBinding.ts';
import { getDocument } from '@core/environment/public.ts';
import { HARDWARE_SOAIBENCH_HISTORY_COPY_ACTION, HARDWARE_SOAIBENCH_HISTORY_DOWNLOAD_ACTION, HARDWARE_SOAIBENCH_HISTORY_MODAL_ID, HARDWARE_SOAIBENCH_HISTORY_ROW_COPY_ACTION, HARDWARE_SOAIBENCH_HISTORY_ROW_DOWNLOAD_ACTION, HARDWARE_SOAIBENCH_HISTORY_SORT_ACTION, HARDWARE_SOAIBENCH_RUN_MODAL_ID, HARDWARE_SYSTEM_INFO_MODAL_ID } from '@features/hardware/public.ts';
import { HARDWARE_ACTION_GPU_SOAIBENCH_HISTORY, HARDWARE_ACTION_GPU_SOAIBENCH_RUN_COPY, HARDWARE_ACTION_GPU_SOAIBENCH_RUN_DOWNLOAD, HARDWARE_ACTION_GPU_SOAIBENCH_START_CONFIRM, HARDWARE_ACTION_SYSTEM_INFO_ANONYMIZE, HARDWARE_ACTION_SYSTEM_INFO_COPY, HARDWARE_ACTION_SYSTEM_INFO_DOWNLOAD, isHardwareActionId } from '@pages/hardware/actions.ts';

type HardwareSystemInfoModalController = {
    handleModalClosed: () => void;
    handleAnonymizeToggle: (event: Event) => void;
    copy: () => Promise<void>;
    download: () => Promise<void>;
};

type SoAIBenchHistoryModalController = {
    handleModalClosed: () => void;
    handleSortAction: (header: HTMLElement) => void;
    copy: () => Promise<void>;
    download: () => Promise<void>;
    copyRun: (runId: string) => Promise<void>;
    downloadRun: (runId: string) => Promise<void>;
};

type SoAIBenchRunModalController = {
    handleModalClosed: () => void;
    handleFooterAction: () => Promise<void>;
    openHistory: () => Promise<void>;
    copyRun: () => Promise<void>;
    downloadRun: () => Promise<void>;
};

type HardwarePageModalEventListenerDependencies = {
    signal: AbortSignal;
    systemInfoModalRoot: HTMLElement;
    soaibenchHistoryModalRoot: HTMLElement;
    soaibenchRunModalRoot: HTMLElement;
    systemInfoModal: HardwareSystemInfoModalController;
    soaibenchHistoryModal: SoAIBenchHistoryModalController;
    soaibenchRunModal: SoAIBenchRunModalController;
};

const bindHardwarePageModalEventListeners = (dependencies: HardwarePageModalEventListenerDependencies): void => {
    const documentRef = getDocument();
    documentRef.addEventListener(
        'core.modal.close',
        (event: Event): void => {
            const target = event.target;
            if (!(target instanceof HTMLElement)) {
                return;
            }
            if (target.id === HARDWARE_SYSTEM_INFO_MODAL_ID) {
                dependencies.systemInfoModal.handleModalClosed();
                return;
            }
            if (target.id === HARDWARE_SOAIBENCH_HISTORY_MODAL_ID) {
                dependencies.soaibenchHistoryModal.handleModalClosed();
                return;
            }
            if (target.id === HARDWARE_SOAIBENCH_RUN_MODAL_ID) {
                dependencies.soaibenchRunModal.handleModalClosed();
            }
        },
        { signal: dependencies.signal }
    );

    bindDataActionListener({
        root: dependencies.systemInfoModalRoot,
        eventType: 'click',
        signal: dependencies.signal,
        isAction: isHardwareActionId,
        mouseButton: 'primary',
        preventDefault: 'never',
        onAction: ({ event, action, actionElement }): void => {
            if (action !== HARDWARE_ACTION_SYSTEM_INFO_COPY && action !== HARDWARE_ACTION_SYSTEM_INFO_DOWNLOAD) {
                return;
            }
            if (shouldPreventDefaultForActionElement(actionElement)) {
                event.preventDefault();
            }
            if (action === HARDWARE_ACTION_SYSTEM_INFO_COPY) {
                terminateHandledPromise(dependencies.systemInfoModal.copy());
                return;
            }
            terminateHandledPromise(dependencies.systemInfoModal.download());
        }
    });
    bindDataActionListener({
        root: dependencies.systemInfoModalRoot,
        eventType: 'change',
        signal: dependencies.signal,
        isAction: isHardwareActionId,
        preventDefault: 'never',
        onAction: ({ event, action }): void => {
            if (action === HARDWARE_ACTION_SYSTEM_INFO_ANONYMIZE) {
                dependencies.systemInfoModal.handleAnonymizeToggle(event);
            }
        }
    });

    bindDataActionListener({
        root: dependencies.soaibenchHistoryModalRoot,
        eventType: 'click',
        signal: dependencies.signal,
        isAction: isHardwareActionId,
        mouseButton: 'primary',
        preventDefault: 'never',
        onAction: ({ event, action, actionElement }): void | Promise<void> => {
            const isHistoryAction = action === HARDWARE_SOAIBENCH_HISTORY_COPY_ACTION || action === HARDWARE_SOAIBENCH_HISTORY_DOWNLOAD_ACTION || action === HARDWARE_SOAIBENCH_HISTORY_SORT_ACTION || action === HARDWARE_SOAIBENCH_HISTORY_ROW_COPY_ACTION || action === HARDWARE_SOAIBENCH_HISTORY_ROW_DOWNLOAD_ACTION;
            if (!isHistoryAction) {
                return;
            }
            if (shouldPreventDefaultForActionElement(actionElement)) {
                event.preventDefault();
            }
            if (action === HARDWARE_SOAIBENCH_HISTORY_COPY_ACTION) {
                return dependencies.soaibenchHistoryModal.copy();
            }
            if (action === HARDWARE_SOAIBENCH_HISTORY_DOWNLOAD_ACTION) {
                return dependencies.soaibenchHistoryModal.download();
            }
            if (action === HARDWARE_SOAIBENCH_HISTORY_ROW_COPY_ACTION || action === HARDWARE_SOAIBENCH_HISTORY_ROW_DOWNLOAD_ACTION) {
                const runId = actionElement.dataset['runId'] ?? '';
                if (!runId) {
                    throw new Error('SoAIBench history row action requires run_id');
                }
                if (action === HARDWARE_SOAIBENCH_HISTORY_ROW_COPY_ACTION) {
                    return dependencies.soaibenchHistoryModal.copyRun(runId);
                }
                return dependencies.soaibenchHistoryModal.downloadRun(runId);
            }
            dependencies.soaibenchHistoryModal.handleSortAction(actionElement);
        }
    });

    bindDataActionListener({
        root: dependencies.soaibenchHistoryModalRoot,
        eventType: 'keydown',
        signal: dependencies.signal,
        isAction: isHardwareActionId,
        preventDefault: 'never',
        onAction: ({ event, action, actionElement }): void => {
            if (action !== HARDWARE_SOAIBENCH_HISTORY_SORT_ACTION) {
                return;
            }
            if (!(event instanceof KeyboardEvent)) {
                return;
            }
            if (event.key !== 'Enter' && event.key !== ' ') {
                return;
            }
            event.preventDefault();
            dependencies.soaibenchHistoryModal.handleSortAction(actionElement);
        }
    });

    bindDataActionListener({
        root: dependencies.soaibenchRunModalRoot,
        eventType: 'click',
        signal: dependencies.signal,
        isAction: isHardwareActionId,
        mouseButton: 'primary',
        preventDefault: 'never',
        onAction: ({ event, action, actionElement }): void => {
            const isRunAction = action === HARDWARE_ACTION_GPU_SOAIBENCH_START_CONFIRM || action === HARDWARE_ACTION_GPU_SOAIBENCH_HISTORY || action === HARDWARE_ACTION_GPU_SOAIBENCH_RUN_COPY || action === HARDWARE_ACTION_GPU_SOAIBENCH_RUN_DOWNLOAD;
            if (!isRunAction) {
                return;
            }
            if (shouldPreventDefaultForActionElement(actionElement)) {
                event.preventDefault();
            }
            if (action === HARDWARE_ACTION_GPU_SOAIBENCH_HISTORY) {
                terminateHandledPromise(dependencies.soaibenchRunModal.openHistory());
                return;
            }
            if (action === HARDWARE_ACTION_GPU_SOAIBENCH_RUN_COPY) {
                terminateHandledPromise(dependencies.soaibenchRunModal.copyRun());
                return;
            }
            if (action === HARDWARE_ACTION_GPU_SOAIBENCH_RUN_DOWNLOAD) {
                terminateHandledPromise(dependencies.soaibenchRunModal.downloadRun());
                return;
            }
            terminateHandledPromise(dependencies.soaibenchRunModal.handleFooterAction());
        }
    });
};

export { bindHardwarePageModalEventListeners };
