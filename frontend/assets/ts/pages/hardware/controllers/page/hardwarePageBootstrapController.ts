/* SoAI - Hardware page bootstrap controller [frontend/assets/ts/pages/hardware/controllers/page/hardwarePageBootstrapController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import { EXPORT_PREVIEW_MODAL_ID, type ExportPreviewModal } from '@features/exportpreview/public.ts';
import { HARDWARE_SOAIBENCH_HISTORY_MODAL_ID, HARDWARE_SOAIBENCH_RUN_MODAL_ID, HARDWARE_SYSTEM_INFO_MODAL_ID, type SoAIBenchHistoryModal, type SoAIBenchRunModal, type SystemInfoModal } from '@features/hardware/public.ts';
import type { HardwareInteractionController } from '@pages/hardware/controllers/interactionController.ts';
import type { HardwareOverflowNavController } from '@pages/hardware/controllers/hardwareOverflowNavController.ts';
import { bindHardwarePageModalEventListeners } from '@pages/hardware/controllers/page/hardwarePageModalEventListenersController.ts';
import { requireHardwareUi } from '@pages/hardware/dom.ts';

interface HardwarePageBootstrapDependencies {
    root: HTMLElement;
    signal: AbortSignal;
    pageDom: PageDom;
    interactionController: HardwareInteractionController;
    overflowNavController: HardwareOverflowNavController;
    systemInfoModal: SystemInfoModal;
    exportPreviewModal: ExportPreviewModal;
    soaibenchHistoryModal: SoAIBenchHistoryModal;
    soaibenchRunModal: SoAIBenchRunModal;
}

const initializeHardwarePageBootstrapController = (dependencies: HardwarePageBootstrapDependencies): void => {
    const modalPresenter = requireModalPresenter();
    const systemInfoModalRoot = modalPresenter.requireElement(HARDWARE_SYSTEM_INFO_MODAL_ID);
    const exportPreviewModalRoot = modalPresenter.requireElement(EXPORT_PREVIEW_MODAL_ID);
    const soaibenchHistoryModalRoot = modalPresenter.requireElement(HARDWARE_SOAIBENCH_HISTORY_MODAL_ID);
    const soaibenchRunModalRoot = modalPresenter.requireElement(HARDWARE_SOAIBENCH_RUN_MODAL_ID);
    dependencies.exportPreviewModal.bindModalEvents({ modalRoot: exportPreviewModalRoot, signal: dependencies.signal });

    bindHardwarePageModalEventListeners({
        signal: dependencies.signal,
        systemInfoModalRoot,
        soaibenchHistoryModalRoot,
        soaibenchRunModalRoot,
        systemInfoModal: dependencies.systemInfoModal,
        soaibenchHistoryModal: dependencies.soaibenchHistoryModal,
        soaibenchRunModal: dependencies.soaibenchRunModal
    });

    const ui = requireHardwareUi(dependencies.pageDom, dependencies.root);

    dependencies.interactionController.bindUi(ui);
    dependencies.overflowNavController.initialize(dependencies.root, dependencies.signal);
};

export { initializeHardwarePageBootstrapController };
export type { HardwarePageBootstrapDependencies };
