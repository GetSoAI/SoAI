/* SoAI - Hardware page modal event listeners controller [frontend/assets/ts/pages/hardware/controllers/page/hardwarePageModalEventListenersController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { shouldPreventDefaultForActionElement } from '@core/dom/dataAction.ts';
import { optionalTrimmedDataAttribute, requireTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { bindDataActionListener } from '@core/dom/dataActionBinding.ts';
import { getDocument } from '@core/environment/public.ts';
import { HARDWARE_SOAIBENCH_HISTORY_COPY_ACTION, HARDWARE_SOAIBENCH_HISTORY_DOWNLOAD_ACTION, HARDWARE_SOAIBENCH_HISTORY_MODAL_ID, HARDWARE_SOAIBENCH_HISTORY_ROW_COPY_ACTION, HARDWARE_SOAIBENCH_HISTORY_ROW_DOWNLOAD_ACTION, HARDWARE_SOAIBENCH_HISTORY_ROW_DELETE_LOCAL_ACTION, HARDWARE_SOAIBENCH_HISTORY_ROW_PUBLISH_ACTION, HARDWARE_SOAIBENCH_HISTORY_SORT_ACTION, HARDWARE_SOAIBENCH_RUN_AGAIN_ACTION, HARDWARE_SOAIBENCH_RUN_COPY_ACTION, HARDWARE_SOAIBENCH_RUN_DISMISS_ACTION, HARDWARE_SOAIBENCH_RUN_DOWNLOAD_ACTION, HARDWARE_SOAIBENCH_RUN_HISTORY_ACTION, HARDWARE_SOAIBENCH_RUN_MODAL_ID, HARDWARE_SOAIBENCH_RUN_NEW_ACTION, HARDWARE_SOAIBENCH_RUN_PICK_ACTION, HARDWARE_SOAIBENCH_RUN_PUBLISH_ACTION, HARDWARE_SOAIBENCH_RUN_RECOVER_ACTION, HARDWARE_SOAIBENCH_RUN_RETRY_ACTION, HARDWARE_SOAIBENCH_RUN_START_ACTION, HARDWARE_SOAIBENCH_RUN_STOP_ACTION, HARDWARE_SYSTEM_INFO_MODAL_ID, type SoAIBenchRunModal } from '@features/hardware/public.ts';
import { HARDWARE_ACTION_SYSTEM_INFO_ANONYMIZE, HARDWARE_ACTION_SYSTEM_INFO_COPY, HARDWARE_ACTION_SYSTEM_INFO_DOWNLOAD, isHardwareActionId, type HardwareActionId } from '@pages/hardware/actions.ts';

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
    deleteLocalRun: (runId: string) => Promise<void>;
    publishRun: (runId: string) => Promise<void>;
};

type SoAIBenchRunModalController = Pick<SoAIBenchRunModal, 'handleModalClosed' | 'handleScroll' | 'showNewBenchmark' | 'dismissComposer' | 'selectGpu' | 'startConfirmed' | 'openHistory' | 'stopRun' | 'copyRun' | 'downloadRun' | 'publishRun' | 'runAgain' | 'retryStart' | 'recoverRun'>;

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
            const isHistoryAction = action === HARDWARE_SOAIBENCH_HISTORY_COPY_ACTION || action === HARDWARE_SOAIBENCH_HISTORY_DOWNLOAD_ACTION || action === HARDWARE_SOAIBENCH_HISTORY_SORT_ACTION || action === HARDWARE_SOAIBENCH_HISTORY_ROW_COPY_ACTION || action === HARDWARE_SOAIBENCH_HISTORY_ROW_DOWNLOAD_ACTION || action === HARDWARE_SOAIBENCH_HISTORY_ROW_PUBLISH_ACTION || action === HARDWARE_SOAIBENCH_HISTORY_ROW_DELETE_LOCAL_ACTION;
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
            if (action === HARDWARE_SOAIBENCH_HISTORY_ROW_COPY_ACTION || action === HARDWARE_SOAIBENCH_HISTORY_ROW_DOWNLOAD_ACTION || action === HARDWARE_SOAIBENCH_HISTORY_ROW_PUBLISH_ACTION || action === HARDWARE_SOAIBENCH_HISTORY_ROW_DELETE_LOCAL_ACTION) {
                const runId = actionElement.dataset['runId'] ?? '';
                if (!runId) {
                    throw new Error('SoAIBench history row action requires run_id');
                }
                if (action === HARDWARE_SOAIBENCH_HISTORY_ROW_COPY_ACTION) {
                    return dependencies.soaibenchHistoryModal.copyRun(runId);
                }
                if (action === HARDWARE_SOAIBENCH_HISTORY_ROW_DELETE_LOCAL_ACTION) {
                    return dependencies.soaibenchHistoryModal.deleteLocalRun(runId);
                }
                if (action === HARDWARE_SOAIBENCH_HISTORY_ROW_PUBLISH_ACTION) {
                    return dependencies.soaibenchHistoryModal.publishRun(runId);
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

    dependencies.soaibenchRunModalRoot.addEventListener('scroll', dependencies.soaibenchRunModal.handleScroll, { capture: true, passive: true, signal: dependencies.signal });

    bindDataActionListener({
        root: dependencies.soaibenchRunModalRoot,
        eventType: 'click',
        signal: dependencies.signal,
        isAction: isHardwareActionId,
        mouseButton: 'primary',
        preventDefault: 'never',
        onAction: ({ event, action, actionElement }): void => {
            const task = dispatchSoAIBenchRunAction(dependencies.soaibenchRunModal, action, actionElement);
            if (task === null) {
                return;
            }
            if (shouldPreventDefaultForActionElement(actionElement)) {
                event.preventDefault();
            }
            terminateHandledPromise(task);
        }
    });
};

const dispatchSoAIBenchRunAction = (modal: SoAIBenchRunModalController, action: HardwareActionId, actionElement: HTMLElement): Promise<void> | null => {
    const sectionId = (): string => requireTrimmedDataAttribute(actionElement, 'soaibenchSection', 'SoAIBench run section action');
    const runId = (): string => requireTrimmedDataAttribute(actionElement, 'runId', 'SoAIBench run action');
    switch (action) {
        case HARDWARE_SOAIBENCH_RUN_NEW_ACTION:
            return modal.showNewBenchmark();
        case HARDWARE_SOAIBENCH_RUN_DISMISS_ACTION:
            return modal.dismissComposer();
        case HARDWARE_SOAIBENCH_RUN_PICK_ACTION:
            return modal.selectGpu(requireTrimmedDataAttribute(actionElement, 'selectionIndex', 'SoAIBench GPU selection'));
        case HARDWARE_SOAIBENCH_RUN_START_ACTION:
            return modal.startConfirmed();
        case HARDWARE_SOAIBENCH_RUN_HISTORY_ACTION:
            return modal.openHistory(optionalTrimmedDataAttribute(actionElement, 'soaibenchSection'));
        case HARDWARE_SOAIBENCH_RUN_STOP_ACTION:
            return modal.stopRun(runId());
        case HARDWARE_SOAIBENCH_RUN_COPY_ACTION:
            return modal.copyRun(runId());
        case HARDWARE_SOAIBENCH_RUN_DOWNLOAD_ACTION:
            return modal.downloadRun(runId());
        case HARDWARE_SOAIBENCH_RUN_PUBLISH_ACTION:
            return modal.publishRun(runId());
        case HARDWARE_SOAIBENCH_RUN_AGAIN_ACTION:
            return modal.runAgain(sectionId());
        case HARDWARE_SOAIBENCH_RUN_RETRY_ACTION:
            return modal.retryStart(sectionId());
        case HARDWARE_SOAIBENCH_RUN_RECOVER_ACTION:
            return modal.recoverRun(sectionId());
        default:
            return null;
    }
};

export { bindHardwarePageModalEventListeners };
