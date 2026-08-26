/* SoAI - Models feature save session [frontend/assets/ts/features/models/modals/saveSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { attachBeforeCloseConfirmationGuard } from '@core/modals/closeGuard.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { showUnsavedChangesConfirmation } from '@core/modals/unsavedChangesConfirmation.ts';
import { createSaveController, SAVE_HEADER_PRIORITY_MODAL, type SaveController } from '@core/save/public.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';

interface ModelModalSaveHost {
    showNotification: (message: string, type: NotificationType, duration?: number) => void;
}

interface ModelModalSaveSessionArguments {
    host: ModelModalSaveHost;
    modal: HTMLElement;
    modalId: string;
    presenter: ModalPresenterApi;
    headerContextId: string;
    saveUnitId?: string | undefined;
    requestContextLabel: string;
    resolveSaveButtons: () => HTMLButtonElement[];
    hasChanges: () => boolean;
    save: () => Promise<void>;
    onBusyChange?: (busy: boolean) => void;
    busyRoots?: HTMLElement[];
}

interface ModelModalSaveSession {
    save: SaveController;
    dispose: () => void;
}

const confirmModelModalDiscard = async (host: ModelModalSaveHost, save: SaveController): Promise<boolean> => {
    if (save.isSaving()) {
        host.showNotification(i18n.t('common.processing'), 'info');
        return false;
    }
    return await showUnsavedChangesConfirmation();
};

const createModelModalSaveSession = (inputArguments: ModelModalSaveSessionArguments): ModelModalSaveSession => {
    const save = createSaveController({
        headerContextId: inputArguments.headerContextId,
        headerPriority: SAVE_HEADER_PRIORITY_MODAL,
        requestContextLabel: inputArguments.requestContextLabel,
        units: [
            {
                id: inputArguments.saveUnitId ?? inputArguments.headerContextId,
                hasChanges: inputArguments.hasChanges,
                save: inputArguments.save
            }
        ]
    });
    save.attach({
        resolveSaveButtons: inputArguments.resolveSaveButtons,
        onBusyChange: inputArguments.onBusyChange,
        busyRoots: inputArguments.busyRoots,
        autoNotifyRoot: inputArguments.modal
    });
    const removeCloseGuard = attachBeforeCloseConfirmationGuard({
        modal: inputArguments.modal,
        presenter: inputArguments.presenter,
        modalId: inputArguments.modalId,
        shouldConfirmClose: () => save.isSaving() || save.hasChanges(),
        confirmClose: async () => await confirmModelModalDiscard(inputArguments.host, save)
    });
    return {
        save,
        dispose: (): void => {
            removeCloseGuard();
            save.dispose();
        }
    };
};

export { confirmModelModalDiscard, createModelModalSaveSession };
export type { ModelModalSaveSession };
