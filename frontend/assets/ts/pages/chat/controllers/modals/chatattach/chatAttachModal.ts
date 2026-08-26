/* SoAI - Chat attach modal page controller [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { bindTypedResolvedDataActionListener } from '@core/dom/dataActionBinding.ts';
import { getRequestAnimationFrame } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import type { TabsComponent } from '@core/ui/controls/Tabs.ts';
import { CHAT_ATTACH_MODAL_ACTIONS, CHAT_ATTACH_MODAL_ID, createCameraCaptureRuntime, isChatAttachModalAction, type ChatAttachCameraRuntime } from '@features/chat/public.ts';
import type { ChatAttachModalHost } from '@pages/chat/controllers/modals/chatattach/contracts.ts';
import { ChatAttachBrowseController } from '@pages/chat/controllers/modals/chatattach/browseController.ts';
import { ChatAttachKnowledgeController } from '@pages/chat/controllers/modals/chatattach/chatAttachKnowledgeController.ts';
import { createChatAttachBrowseElements, createChatAttachCameraElements, createChatAttachKnowledgeElements, createChatAttachSoaiLinkElements, createChatAttachUploadElements, requireChatAttachModalChild } from '@pages/chat/controllers/modals/chatattach/chatAttachModalElementsManager.ts';
import { activateChatAttachTab, createChatAttachTabsComponent, requireChatAttachTabAvailable, resolveInitialChatAttachTab, syncChatAttachTabAvailability, type ChatAttachModalOpenOptions, type ChatAttachModalTab } from '@pages/chat/controllers/modals/chatattach/chatAttachModalTabsController.ts';
import { ChatAttachSoaiLinkController } from '@pages/chat/controllers/modals/chatattach/ChatAttachSoaiLinkController.ts';
import { ChatAttachUploadController } from '@pages/chat/controllers/modals/chatattach/chatAttachUploadController.ts';

interface ChatAttachModalRuntime {
    cameraRuntime: ChatAttachCameraRuntime;
    browseController: ChatAttachBrowseController;
    knowledgeController: ChatAttachKnowledgeController;
    soaiLinkController: ChatAttachSoaiLinkController;
    uploadController: ChatAttachUploadController;
    tabsComponent: TabsComponent;
}

type ChatAttachModalSession = { controller: AbortController; runtime: ChatAttachModalRuntime };

const modalSessions: WeakMap<HTMLElement, ChatAttachModalSession> = new WeakMap();

const selectTab = async (host: ChatAttachModalHost, modal: HTMLElement, runtime: ChatAttachModalRuntime, tab: ChatAttachModalTab): Promise<void> => {
    requireChatAttachTabAvailable(host, tab);
    activateChatAttachTab(modal, tab);
    modal.dataset['chatAttachActiveTab'] = tab;
    if (tab === 'camera') {
        runtime.uploadController.deactivate();
        runtime.browseController.deactivate();
        runtime.knowledgeController.deactivate();
        runtime.soaiLinkController.deactivate();
        await runtime.cameraRuntime.activate();
        return;
    }
    runtime.cameraRuntime.deactivate();
    if (tab === 'browse') {
        runtime.uploadController.deactivate();
        runtime.knowledgeController.deactivate();
        runtime.soaiLinkController.deactivate();
        runtime.browseController.activate();
        return;
    }
    runtime.browseController.deactivate();
    if (tab === 'soaiLink') {
        runtime.uploadController.deactivate();
        runtime.knowledgeController.deactivate();
        runtime.soaiLinkController.activate();
        return;
    }
    runtime.soaiLinkController.deactivate();
    if (tab === 'knowledge') {
        runtime.uploadController.deactivate();
        runtime.knowledgeController.activate();
        return;
    }
    runtime.knowledgeController.deactivate();
    runtime.uploadController.activate();
};

const syncActionAvailability = (host: ChatAttachModalHost, runtime: ChatAttachModalRuntime): void => {
    syncChatAttachTabAvailability(host, runtime.tabsComponent);
    runtime.cameraRuntime.setAvailable(host.attachments.cameraEnabled());
};

const resolveInitialFocusTokens = (tab: ChatAttachModalTab): readonly string[] => {
    if (tab === 'camera') {
        return ['camera-shutter'];
    }
    if (tab === 'browse') {
        return ['search'];
    }
    if (tab === 'soaiLink') {
        return ['soai-link-input'];
    }
    if (tab === 'knowledge') {
        return ['knowledge-dropzone', 'knowledge-file-button', 'knowledge-folder-button'];
    }
    return ['dropzone', 'upload-file-button', 'upload-folder-button'];
};

const focusInitialTabControl = (modal: HTMLElement, tab: ChatAttachModalTab): void => {
    getRequestAnimationFrame()(() => {
        for (const token of resolveInitialFocusTokens(tab)) {
            const element = requireChatAttachModalChild(modal, token);
            if (element instanceof HTMLElement && !element.hidden && element.getClientRects().length > 0 && (!(element instanceof HTMLButtonElement) || !element.disabled)) {
                element.focus({ preventScroll: true });
                return;
            }
        }
    });
};

const useCapturedCameraFile = async (host: ChatAttachModalHost, cameraRuntime: ChatAttachCameraRuntime): Promise<void> => {
    const file = await cameraRuntime.useCapturedFile();
    if (file === null) {
        return;
    }
    requireModalPresenter().close(CHAT_ATTACH_MODAL_ID);
    await host.attachments.captureCamera(file);
};

const createAttachModalRuntime = async (host: ChatAttachModalHost, modal: HTMLElement, initialTab: ChatAttachModalTab): Promise<ChatAttachModalSession> => {
    const controller = new AbortController();
    const cameraRuntime = createCameraCaptureRuntime(createChatAttachCameraElements(modal), controller.signal);
    const browseElements = createChatAttachBrowseElements(modal);
    const browseController = new ChatAttachBrowseController(host, browseElements, controller.signal);
    const knowledgeController = new ChatAttachKnowledgeController(host, createChatAttachKnowledgeElements(modal), controller.signal);
    const uploadController = new ChatAttachUploadController(host, createChatAttachUploadElements(modal), controller.signal);
    const soaiLinkController = new ChatAttachSoaiLinkController(host, createChatAttachSoaiLinkElements(modal), controller.signal);
    let runtime: ChatAttachModalRuntime;
    const tabsComponent = await createChatAttachTabsComponent(modal, initialTab, (tab) => host.execution.run('chat:attachModalTabChange', () => selectTab(host, modal, runtime, tab)));
    runtime = { cameraRuntime, browseController, knowledgeController, soaiLinkController, uploadController, tabsComponent };
    const session = { controller, runtime };
    modalSessions.set(modal, session);
    const handleModalClose = (): void => {
        runtime.uploadController.deactivate();
        runtime.knowledgeController.deactivate();
        runtime.soaiLinkController.deactivate();
        controller.abort();
        modalSessions.delete(modal);
        runtime.tabsComponent.destroy().catch((error) => {
            const runtimeError = ensureError(error);
            errorHandler.warn('ChatAttachModal', 'Failed to destroy attach modal tabs', runtimeError);
        });
    };
    const handleBrowseInput = (): void => browseController.handleInput();
    modal.addEventListener('core.modal.close', handleModalClose, { signal: controller.signal });
    browseElements.searchInput.addEventListener('input', handleBrowseInput, { signal: controller.signal });
    bindTypedResolvedDataActionListener({
        root: modal,
        signal: controller.signal,
        eventType: 'click',
        isAction: isChatAttachModalAction,
        preventDefault: 'always',
        onAction: async ({ action, actionElement, event }): Promise<void> => {
            if (action === CHAT_ATTACH_MODAL_ACTIONS.BROWSE_SELECT) {
                browseController.selectResult(host.presentation.actionData(actionElement, 'resultKey'), actionElement, event);
                return;
            }
            if (action === CHAT_ATTACH_MODAL_ACTIONS.BROWSE_OPEN) {
                await browseController.openResult(host.presentation.actionData(actionElement, 'resultKey'), actionElement, event);
                return;
            }
            if (action === CHAT_ATTACH_MODAL_ACTIONS.BROWSE_SORT) {
                browseController.sortResults(host.presentation.actionData(actionElement, 'sort'));
                return;
            }
            if (action === CHAT_ATTACH_MODAL_ACTIONS.BROWSE_CHANGE_WORKSPACE_PATH) {
                await browseController.openWorkspacePathPicker();
                return;
            }
            if (action === CHAT_ATTACH_MODAL_ACTIONS.BROWSE_PREVIEW) {
                await browseController.previewSelected();
                return;
            }
            if (action === CHAT_ATTACH_MODAL_ACTIONS.BROWSE_ATTACH) {
                if (await browseController.attachSelected()) {
                    requireModalPresenter().close(CHAT_ATTACH_MODAL_ID);
                }
                return;
            }
            if (action === CHAT_ATTACH_MODAL_ACTIONS.CHOOSE_UPLOAD) {
                requireChatAttachTabAvailable(host, 'upload');
                runtime.uploadController.openPrimaryPicker();
                return;
            }
            if (action === CHAT_ATTACH_MODAL_ACTIONS.CHOOSE_KNOWLEDGE_UPLOAD) {
                runtime.knowledgeController.openPrimaryPicker();
                return;
            }
            if (action === CHAT_ATTACH_MODAL_ACTIONS.CHOOSE_FILE) {
                requireChatAttachTabAvailable(host, 'upload');
                runtime.uploadController.openFiles();
                return;
            }
            if (action === CHAT_ATTACH_MODAL_ACTIONS.CHOOSE_FOLDER) {
                requireChatAttachTabAvailable(host, 'upload');
                runtime.uploadController.openFolder();
                return;
            }
            if (action === CHAT_ATTACH_MODAL_ACTIONS.ATTACH_FOLDER) {
                runtime.knowledgeController.openFolder();
                return;
            }
            if (action === CHAT_ATTACH_MODAL_ACTIONS.KNOWLEDGE_IMPORT) {
                await runtime.knowledgeController.importFromFileExplorer();
                return;
            }
            if (action === CHAT_ATTACH_MODAL_ACTIONS.KNOWLEDGE_REINDEX) {
                await runtime.knowledgeController.reindex();
                return;
            }
            if (action === CHAT_ATTACH_MODAL_ACTIONS.CAMERA_SHUTTER) {
                requireChatAttachTabAvailable(host, 'camera');
                await cameraRuntime.capture();
                return;
            }
            if (action === CHAT_ATTACH_MODAL_ACTIONS.CAMERA_RETAKE) {
                requireChatAttachTabAvailable(host, 'camera');
                await cameraRuntime.retake();
                return;
            }
            if (action === CHAT_ATTACH_MODAL_ACTIONS.CAMERA_USE) {
                requireChatAttachTabAvailable(host, 'camera');
                await useCapturedCameraFile(host, cameraRuntime);
                return;
            }
            if (action === CHAT_ATTACH_MODAL_ACTIONS.CAMERA_FLIP) {
                requireChatAttachTabAvailable(host, 'camera');
                await cameraRuntime.flipCamera();
                return;
            }
            if (action === CHAT_ATTACH_MODAL_ACTIONS.ATTACH_DOCUMENTS) {
                runtime.knowledgeController.openDocuments();
            }
        }
    });
    return session;
};

const requireAttachModalRuntime = async (host: ChatAttachModalHost, modal: HTMLElement, initialTab: ChatAttachModalTab): Promise<ChatAttachModalRuntime> => {
    const existingSession = modalSessions.get(modal);
    if (existingSession) {
        return existingSession.runtime;
    }
    const session = await createAttachModalRuntime(host, modal, initialTab);
    return session.runtime;
};

const openChatAttachModal = (host: ChatAttachModalHost, options: ChatAttachModalOpenOptions = {}): void => {
    const presenter = requireModalPresenter();
    const modal = presenter.requireElement(CHAT_ATTACH_MODAL_ID);
    host.execution.run('chat:attachModalOpen', async () => {
        const initialTab = resolveInitialChatAttachTab(modal, options);
        const runtime = await requireAttachModalRuntime(host, modal, initialTab);
        syncActionAvailability(host, runtime);
        await selectTab(host, modal, runtime, initialTab);
        presenter.open(CHAT_ATTACH_MODAL_ID);
        focusInitialTabControl(modal, initialTab);
    });
};

export { openChatAttachModal };
