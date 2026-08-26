/* SoAI - Chat configuration modal close protection [frontend/assets/ts/pages/chat/controllers/chatpage/configuration/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { attachBeforeCloseConfirmationGuard, attachPendingOperationCloseGuard } from '@core/modals/closeGuard.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { showUnsavedChangesConfirmation } from '@core/modals/unsavedChangesConfirmation.ts';
import { CHAT_CONFIGURATION_MODAL_ID } from '@features/chat/public.ts';
import type { ChatConfigurationController } from '@pages/chat/controllers/chatconfigurationcontroller/ChatConfigurationController.ts';

interface ChatConfigurationCloseGuardOptions {
    modal: HTMLElement;
    configuration: ChatConfigurationController;
    hasPresetDraft(): boolean;
    signal: AbortSignal;
}

const attachChatConfigurationCloseGuards = (options: ChatConfigurationCloseGuardOptions): void => {
    const isPending = (): boolean => options.configuration.operationGate().activeOperation() !== null;
    const detachPendingGuard = attachPendingOperationCloseGuard({ modal: options.modal, isPending });
    const detachDirtyGuard = attachBeforeCloseConfirmationGuard({
        modal: options.modal,
        presenter: requireModalPresenter(),
        modalId: CHAT_CONFIGURATION_MODAL_ID,
        shouldConfirmClose: () => !isPending() && (options.configuration.hasPendingChanges() || options.hasPresetDraft()),
        confirmClose: showUnsavedChangesConfirmation
    });
    options.signal.addEventListener('abort', detachPendingGuard, { once: true });
    options.signal.addEventListener('abort', detachDirtyGuard, { once: true });
};

export { attachChatConfigurationCloseGuards };
