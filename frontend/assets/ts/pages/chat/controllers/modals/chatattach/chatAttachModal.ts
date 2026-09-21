/* SoAI - Chat attach modal page controller [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { bindTypedResolvedDataActionListener } from '@core/dom/dataActionBinding.ts';
import { checkerboardService } from '@core/dom/dom.ts';
import { getRequestAnimationFrame } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import type { TabsComponent } from '@core/ui/controls/Tabs.ts';
import { CHAT_ATTACH_MODAL_ACTIONS, CHAT_ATTACH_MODAL_ID, createCameraCaptureRuntime, isChatAttachModalAction, type ChatAttachCameraRuntime } from '@features/chat/public.ts';
import type { ChatAttachModalHost } from '@pages/chat/controllers/modals/chatattach/contracts.ts';
import type { ChatAttachDraftRemovalSource } from '@pages/chat/controllers/actionhandlers/core/contracts.ts';
import { ChatAttachBrowseController } from '@pages/chat/controllers/modals/chatattach/browseController.ts';
import { ChatAttachKnowledgeController } from '@pages/chat/controllers/modals/chatattach/chatAttachKnowledgeController.ts';
import { createChatAttachBrowseElements, createChatAttachCameraElements, createChatAttachDraftListElements, createChatAttachKnowledgeElements, createChatAttachSoaiLinkElements, createChatAttachUploadElements, requireChatAttachModalButton, requireChatAttachModalChild } from '@pages/chat/controllers/modals/chatattach/chatAttachModalElementsManager.ts';
import { activateChatAttachTab, createChatAttachTabsComponent, requireChatAttachTabAvailable, resolveInitialChatAttachTab, syncChatAttachTabAvailability, syncChatAttachTabBadges, type ChatAttachModalOpenOptions, type ChatAttachModalTab } from '@pages/chat/controllers/modals/chatattach/chatAttachModalTabsController.ts';
import { ChatAttachDraftAttachmentListController } from '@pages/chat/controllers/modals/chatattach/ChatAttachDraftAttachmentListController.ts';
import { ChatAttachSoaiLinkController } from '@pages/chat/controllers/modals/chatattach/ChatAttachSoaiLinkController.ts';
import { ChatAttachUploadController } from '@pages/chat/controllers/modals/chatattach/chatAttachUploadController.ts';
import { setButtonEnabled } from '@pages/chat/controllers/modals/chatattach/view.ts';

interface ChatAttachModalRuntime {
    cameraRuntime: ChatAttachCameraRuntime;
    cameraDraftListController: ChatAttachDraftAttachmentListController;
    browseController: ChatAttachBrowseController;
    knowledgeController: ChatAttachKnowledgeController;
    soaiLinkController: ChatAttachSoaiLinkController;
    uploadController: ChatAttachUploadController;
    tabsComponent: TabsComponent;
    removeAllButtons: ReadonlyMap<ChatAttachDraftRemovalSource, HTMLButtonElement>;
    pendingRemovalSources: Set<ChatAttachDraftRemovalSource>;
}

type ChatAttachModalSession = { controller: AbortController; runtime: ChatAttachModalRuntime };

type ChatAttachCheckerboardTarget = { token: string; itemSelector: string };

const modalSessions: WeakMap<HTMLElement, ChatAttachModalSession> = new WeakMap();
const removalSources: readonly ChatAttachDraftRemovalSource[] = ['upload', 'camera', 'browse', 'soaiLink', 'knowledge'];

const resolveChatAttachCheckerboardTarget = (tab: ChatAttachModalTab): ChatAttachCheckerboardTarget | null => {
    if (tab === 'upload') return { token: 'upload-list', itemSelector: '.chat-attach-draft-attachment-row' };
    if (tab === 'camera') return { token: 'camera-list', itemSelector: '.chat-attach-draft-attachment-row' };
    if (tab === 'browse') return { token: 'browse-list', itemSelector: '.chat-attach-draft-attachment-row' };
    if (tab === 'soaiLink') return { token: 'soai-link-list', itemSelector: '.chat-attach-draft-attachment-row' };
    if (tab === 'knowledge') return { token: 'knowledge-documents-list', itemSelector: '.rag-document-item' };
    return null;
};

const refreshVisibleChatAttachCheckerboard = (modal: HTMLElement, tab: ChatAttachModalTab): void => {
    const target = resolveChatAttachCheckerboardTarget(tab);
    if (target === null) return;
    getRequestAnimationFrame()(() => {
        if (!modal.isConnected || modal.dataset['chatAttachActiveTab'] !== tab) return;
        checkerboardService.updateCheckerboard(requireChatAttachModalChild(modal, target.token), target.itemSelector);
    });
};

const selectTab = async (host: ChatAttachModalHost, modal: HTMLElement, runtime: ChatAttachModalRuntime, tab: ChatAttachModalTab): Promise<void> => {
    requireChatAttachTabAvailable(host, tab);
    activateChatAttachTab(modal, tab);
    modal.dataset['chatAttachActiveTab'] = tab;
    refreshVisibleChatAttachCheckerboard(modal, tab);
    runtime.cameraRuntime.deactivate();
    runtime.cameraDraftListController.deactivate();
    runtime.browseController.deactivate();
    runtime.knowledgeController.deactivate();
    runtime.soaiLinkController.deactivate();
    runtime.uploadController.deactivate();
    if (tab === 'camera') {
        runtime.cameraDraftListController.activate();
        await runtime.cameraRuntime.activate();
        return;
    }
    if (tab === 'browse') {
        runtime.browseController.activate();
        return;
    }
    if (tab === 'soaiLink') {
        runtime.soaiLinkController.activate();
        return;
    }
    if (tab === 'knowledge') {
        runtime.knowledgeController.activate();
        return;
    }
    runtime.uploadController.activate();
};

const syncRemoveAllButton = (host: ChatAttachModalHost, runtime: ChatAttachModalRuntime): void => {
    const counts = host.attachments.draftCounts();
    for (const source of removalSources) {
        const button = runtime.removeAllButtons.get(source);
        if (button === undefined) throw new Error(`Chat attach modal requires the ${source} remove-all button`);
        const hasDrafts = counts[source] > 0;
        button.hidden = !hasDrafts;
        setButtonEnabled(button, hasDrafts && !runtime.pendingRemovalSources.has(source));
    }
};

const resolveRemovalSource = (runtime: ChatAttachModalRuntime, actionElement: HTMLElement): ChatAttachDraftRemovalSource => {
    const source = removalSources.find((candidate) => runtime.removeAllButtons.get(candidate) === actionElement);
    if (source === undefined) throw new Error('Chat attach modal remove-all action has no owning tab');
    return source;
};

const syncActionAvailability = (host: ChatAttachModalHost, runtime: ChatAttachModalRuntime): void => {
    syncChatAttachTabAvailability(host, runtime.tabsComponent);
    syncChatAttachTabBadges(host, runtime.tabsComponent);
    runtime.cameraRuntime.setAvailable(host.attachments.cameraEnabled());
    syncRemoveAllButton(host, runtime);
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
    const cameraDraftListController = new ChatAttachDraftAttachmentListController(host, createChatAttachDraftListElements(modal, 'camera'), controller.signal, 'camera');
    const browseElements = createChatAttachBrowseElements(modal);
    const browseController = new ChatAttachBrowseController(host, browseElements, controller.signal);
    const knowledgeController = new ChatAttachKnowledgeController(host, createChatAttachKnowledgeElements(modal), controller.signal);
    const uploadController = new ChatAttachUploadController(host, createChatAttachUploadElements(modal), controller.signal);
    const soaiLinkController = new ChatAttachSoaiLinkController(host, createChatAttachSoaiLinkElements(modal), controller.signal);
    const removeAllButtons = new Map<ChatAttachDraftRemovalSource, HTMLButtonElement>(removalSources.map((source) => [source, requireChatAttachModalButton(modal, `${source === 'soaiLink' ? 'soai-link' : source}-remove-all`)]));
    let runtime: ChatAttachModalRuntime;
    const tabsComponent = await createChatAttachTabsComponent(modal, initialTab, (tab) => host.execution.run('chat:attachModalTabChange', () => selectTab(host, modal, runtime, tab)));
    runtime = { cameraRuntime, cameraDraftListController, browseController, knowledgeController, soaiLinkController, uploadController, tabsComponent, removeAllButtons, pendingRemovalSources: new Set() };
    const session = { controller, runtime };
    modalSessions.set(modal, session);
    const syncDraftPresentation = (): void => {
        syncChatAttachTabBadges(host, runtime.tabsComponent);
        syncRemoveAllButton(host, runtime);
    };
    const unsubscribeDrafts = host.attachments.subscribeDrafts(syncDraftPresentation);
    const unsubscribeRag = host.rag.subscribe(syncDraftPresentation);
    controller.signal.addEventListener(
        'abort',
        () => {
            unsubscribeDrafts();
            unsubscribeRag();
        },
        { once: true }
    );
    const handleModalClose = (): void => {
        runtime.uploadController.deactivate();
        runtime.cameraDraftListController.deactivate();
        runtime.browseController.deactivate();
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
            if (action === CHAT_ATTACH_MODAL_ACTIONS.REMOVE_ALL) {
                const source = resolveRemovalSource(runtime, actionElement);
                if (runtime.pendingRemovalSources.has(source)) return;
                runtime.pendingRemovalSources.add(source);
                syncRemoveAllButton(host, runtime);
                try {
                    await host.attachments.removeAll(source);
                } finally {
                    runtime.pendingRemovalSources.delete(source);
                    syncRemoveAllButton(host, runtime);
                }
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
            if (action === CHAT_ATTACH_MODAL_ACTIONS.CAMERA_SWITCH) {
                requireChatAttachTabAvailable(host, 'camera');
                await cameraRuntime.switchCamera();
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
        const initialTab = resolveInitialChatAttachTab(host, modal, options);
        const runtime = await requireAttachModalRuntime(host, modal, initialTab);
        syncActionAvailability(host, runtime);
        await selectTab(host, modal, runtime, initialTab);
        presenter.open(CHAT_ATTACH_MODAL_ID);
        focusInitialTabControl(modal, initialTab);
    });
};

export { openChatAttachModal };
