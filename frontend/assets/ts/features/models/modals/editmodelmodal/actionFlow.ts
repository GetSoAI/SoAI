/* SoAI - Models feature action flow [frontend/assets/ts/features/models/modals/editmodelmodal/actionFlow.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { SaveController } from '@core/save/public.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { confirmModelModalDiscard } from '@features/models/modals/saveSession.ts';

interface EditModelActionFlowHost {
    modals: ModalPresenterApi;
    runWithBoundary<T>(operation: string, task: () => Promise<T>): Promise<T>;
    showNotification(message: string, type: NotificationType, duration?: number): void;
    navigateToModelDetail(model: ModelRecord, options?: { tab?: string; action?: string }): void;
    showRenameModelModal(model: ModelRecord): void;
    deleteModel(model: ModelRecord): Promise<void>;
}

const canLeaveEditModelModal = async (host: EditModelActionFlowHost, save: SaveController | null): Promise<boolean> => {
    return !save || (!save.isSaving() && !save.hasChanges()) || (await confirmModelModalDiscard(host, save));
};

const closeEditModelModalForAction = (host: EditModelActionFlowHost, modalId: string, reason: string): void => {
    host.modals.close(modalId, { force: true, restoreFocus: false, reason });
};

const navigateFromEditModelModal = async (host: EditModelActionFlowHost, modalId: string, save: SaveController | null, model: ModelRecord, options: { tab?: string; action?: string }): Promise<void> => {
    if (!(await canLeaveEditModelModal(host, save))) {
        return;
    }
    closeEditModelModalForAction(host, modalId, 'navigate');
    host.navigateToModelDetail(model, options);
};

const renameFromEditModelModal = async (host: EditModelActionFlowHost, modalId: string, save: SaveController | null, model: ModelRecord): Promise<void> => {
    if (!(await canLeaveEditModelModal(host, save))) {
        return;
    }
    closeEditModelModalForAction(host, modalId, 'rename');
    host.showRenameModelModal(model);
};

const deleteFromEditModelModal = async (host: EditModelActionFlowHost, modalId: string, save: SaveController | null, model: ModelRecord): Promise<void> => {
    if (!(await canLeaveEditModelModal(host, save))) {
        return;
    }
    closeEditModelModalForAction(host, modalId, 'delete');
    await host.runWithBoundary('models:deleteFromEditModelModal', async () => await host.deleteModel(model));
};

export { deleteFromEditModelModal, navigateFromEditModelModal, renameFromEditModelModal };
export type { EditModelActionFlowHost };
