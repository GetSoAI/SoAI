/* SoAI - Chat consumer wiring for the reusable attachment dialog [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { ATTACH_MODAL_ACTIONS, ATTACH_MODAL_TABS, AttachUploadController, AttachModalController, createAttachBrowseElements, createAttachDraftListElements, createAttachKnowledgeElements, createAttachLinkElements, createAttachUploadElements, type AttachModalAction, type AttachModalContent, type AttachModalSessionContext, type AttachModalTab } from '@features/attachmodal/public.ts';
import { resolveChatConfigurationTabLabel } from '@features/chat/public.ts';
import type { ChatAttachModalHost } from '@pages/chat/controllers/modals/chatattach/contracts.ts';
import { createChatAttachBrowseController } from '@pages/chat/controllers/modals/chatattach/browseController.ts';
import { ChatAttachKnowledgeController } from '@pages/chat/controllers/modals/chatattach/chatAttachKnowledgeController.ts';
import { createChatAttachDraftList } from '@pages/chat/controllers/modals/chatattach/chatAttachDraftListController.ts';
import { createChatAttachLinkController } from '@pages/chat/controllers/modals/chatattach/chatAttachLinkController.ts';
import { resolveChatAttachDroppedPayloadType } from '@pages/chat/controllers/modals/chatattach/chatAttachDroppedPayloadController.ts';

const disabledTabLabel = (tab: AttachModalTab): string => {
    const setting = tab === 'camera' ? i18n.t('chat.configuration.inputActions.camera') : i18n.t('chat.configuration.inputActions.uploadFile');
    const action = tab === 'camera' ? i18n.t('chat.attachModal.tabCamera') : i18n.t('chat.attachModal.tabUpload');
    const reason = i18n.t('chat.attachModal.tabDisabledReason', { setting, tab: resolveChatConfigurationTabLabel('appearance') });
    return i18n.t('chat.inputActions.disabledWithReason', { action, reason });
};

const createChatAttachContent = (host: ChatAttachModalHost, context: AttachModalSessionContext): AttachModalContent => {
    const { modal, signal } = context;
    const cameraDrafts = createChatAttachDraftList(host, createAttachDraftListElements(modal, 'camera'), signal, 'camera');
    context.addCleanup(() => cameraDrafts.deactivate());
    const browseElements = createAttachBrowseElements(modal);
    const browse = createChatAttachBrowseController(host, browseElements, signal);
    context.addCleanup(() => browse.deactivate());
    const knowledge = new ChatAttachKnowledgeController(host, createAttachKnowledgeElements(modal), signal);
    context.addCleanup(() => knowledge.deactivate());
    const uploadElements = createAttachUploadElements(modal);
    const upload = new AttachUploadController(
        {
            isEnabled: () => host.attachments.fileUploadEnabled(),
            allowFolders: true,
            beforePicker: () => host.conversation.actions.collapseSidebarIfNarrowViewport(),
            fileInput: () => host.attachments.requireFileInput(),
            folderInput: () => host.attachments.requireFolderInput(),
            captureUpload: () => {
                const intake = host.attachments.captureIntake();
                return (files, source) => (source === 'folder' ? host.attachments.uploadFolder(files, intake) : host.attachments.uploadFiles(files, intake));
            },
            classifyDrop: resolveChatAttachDroppedPayloadType,
            run: (task) => host.execution.run('chat:attachModalUploadDrop', task),
            setTimer: (callback, delay) => host.shared.pageResources.setTimer(callback, delay),
            clearTimer: (id) => host.shared.pageResources.clearTimer(id)
        },
        uploadElements,
        signal,
        createChatAttachDraftList(host, uploadElements.draftList, signal, 'upload')
    );
    context.addCleanup(() => upload.deactivate());
    const links = createChatAttachLinkController(host, createAttachLinkElements(modal), signal);
    context.addCleanup(() => links.deactivate());
    browseElements.searchInput.addEventListener(
        'input',
        () => {
            if (context.isCurrent()) browse.handleInput();
        },
        { signal }
    );
    const handleAction = async (action: AttachModalAction, element: HTMLElement, event: Event): Promise<boolean> => {
        if (!context.isCurrent()) return false;
        if (action === ATTACH_MODAL_ACTIONS.BROWSE_SELECT) browse.selectResult(host.presentation.actionData(element, 'resultKey'), element, event);
        if (action === ATTACH_MODAL_ACTIONS.BROWSE_OPEN) await browse.openResult(host.presentation.actionData(element, 'resultKey'), element, event);
        if (action === ATTACH_MODAL_ACTIONS.BROWSE_SORT) browse.sortResults(host.presentation.actionData(element, 'sort'));
        if (action === ATTACH_MODAL_ACTIONS.BROWSE_CHANGE_WORKSPACE_PATH) await browse.openWorkspacePathPicker();
        if (action === ATTACH_MODAL_ACTIONS.BROWSE_PREVIEW) await browse.previewSelected();
        if (action === ATTACH_MODAL_ACTIONS.BROWSE_ATTACH) return await browse.attachSelected();
        if (action === ATTACH_MODAL_ACTIONS.CHOOSE_UPLOAD) upload.openPrimaryPicker();
        if (action === ATTACH_MODAL_ACTIONS.CHOOSE_FILE) upload.openFiles();
        if (action === ATTACH_MODAL_ACTIONS.CHOOSE_FOLDER) upload.openFolder();
        if (action === ATTACH_MODAL_ACTIONS.CHOOSE_KNOWLEDGE_UPLOAD) knowledge.openPrimaryPicker();
        if (action === ATTACH_MODAL_ACTIONS.ATTACH_FOLDER) knowledge.openFolder();
        if (action === ATTACH_MODAL_ACTIONS.KNOWLEDGE_IMPORT) await knowledge.importFromFileExplorer();
        if (action === ATTACH_MODAL_ACTIONS.KNOWLEDGE_REINDEX) await knowledge.reindex();
        if (action === ATTACH_MODAL_ACTIONS.ATTACH_DOCUMENTS) knowledge.openDocuments();
        return false;
    };
    return {
        activate: (tab) => {
            if (tab === 'camera') cameraDrafts.activate();
            if (tab === 'browse') browse.activate();
            if (tab === 'knowledge') knowledge.activate();
            if (tab === 'soaiLink') links.activate();
            if (tab === 'upload') upload.activate();
        },
        deactivate: () => {
            const failures: Error[] = [];
            for (const pane of [cameraDrafts, browse, knowledge, upload, links]) runCleanupStepCollectingFailure(() => pane.deactivate(), failures);
            throwCollectedCleanupFailures(failures);
        },
        handleAction
    };
};

const createChatAttachModalController = (host: ChatAttachModalHost): AttachModalController =>
    new AttachModalController({
        policy: { enabledTabs: ATTACH_MODAL_TABS, acceptedMedia: ['image', 'audio', 'video', 'document'], allowFolders: true },
        presenter: requireModalPresenter(),
        signal: () => host.shared.signal(),
        isAvailable: (tab) => (tab === 'upload' ? host.attachments.fileUploadEnabled() : tab === 'camera' ? host.attachments.cameraEnabled() : true),
        disabledLabel: disabledTabLabel,
        counts: () => host.attachments.draftCounts(),
        subscribeChanges: (handler) => {
            const unsubscribeDrafts = host.attachments.subscribeDrafts(handler);
            const unsubscribeKnowledge = host.rag.subscribe(handler);
            return () => {
                const failures: Error[] = [];
                runCleanupStepCollectingFailure(unsubscribeDrafts, failures);
                runCleanupStepCollectingFailure(unsubscribeKnowledge, failures);
                throwCollectedCleanupFailures(failures);
            };
        },
        createContent: (context) => createChatAttachContent(host, context),
        captureCamera: () => {
            const intake = host.attachments.captureIntake();
            return { scope: intake.scope, submit: (file) => host.attachments.captureCamera(file, intake) };
        },
        removeAll: (tab) => host.attachments.removeAll(tab),
        run: (operation, task) => host.execution.run(operation, task),
        reportCleanupFailure: (error) => host.shared.feedback.handle(error, 'Attachment dialog cleanup failed', { notify: false })
    });

export { createChatAttachModalController };
