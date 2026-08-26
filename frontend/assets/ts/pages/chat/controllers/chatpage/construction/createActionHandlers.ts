/* SoAI - Chat page create action handlers [frontend/assets/ts/pages/chat/controllers/chatpage/construction/createActionHandlers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isString, isThenable } from '@core/typeGuards.ts';
import { buildDraftAttachmentOverflowRecords, type ChatActionId, type ChatInputActionName } from '@features/chat/public.ts';
import { createChatActionHandlers } from '@pages/chat/controllers/actionhandlers/chatActionHandlers.ts';
import type { ChatActionHandlersHost } from '@pages/chat/controllers/actionhandlers/core/contracts.ts';
import { toggleFavoritesAtTop } from '@pages/chat/controllers/chatUiBehaviors.ts';
import type { ChatActionHandlerDependencies } from '@pages/chat/controllers/chatpage/construction/contracts.ts';
import { startAgentPlanExecution, type AgentPlanExecutionHost } from '@pages/chat/controllers/page/actions/agentPlanExecutionController.ts';
import { copyCodeBlock, type CopyCodeBlockHost } from '@pages/chat/controllers/page/actions/copyCodeBlock.ts';
import { copyInlineMediaReference, type CopyInlineMediaReferenceHost } from '@pages/chat/controllers/page/actions/inlineMediaReferenceCopyController.ts';
import { openInlineMediaLocalFolder, type OpenInlineMediaLocalFolderHost } from '@pages/chat/controllers/page/actions/openInlineMediaLocalFolderController.ts';

const runNavigationOperation = (operationId: string, operation: () => void | Promise<void>): void => {
    try {
        const result = operation();
        if (!isThenable(result)) {
            return;
        }
        result.then(
            () => undefined,
            (error: Error): void => {
                errorHandler.warn('ChatPage', `Chat navigation failed: ${operationId}`, error);
            }
        );
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn('ChatPage', `Chat navigation failed: ${operationId}`, runtimeError);
    }
};

const requireUploadInput = (page: ChatActionHandlerDependencies, selector: string, label: string): HTMLInputElement => {
    const input = page.page.pageDom.requireHTMLElement(selector);
    if (!(input instanceof HTMLInputElement)) {
        throw new TypeError(`${label} must be an input element`);
    }
    return input;
};

const requireChatInput = (page: ChatActionHandlerDependencies): HTMLTextAreaElement => {
    const input = page.page.pageDom.requireHTMLElement('.chat-input');
    if (!(input instanceof HTMLTextAreaElement)) {
        throw new TypeError('Chat input must be a textarea element');
    }
    return input;
};

const requireInputActionEnabled = (action: ChatInputActionName, enabled: boolean): void => {
    if (!enabled) {
        throw new Error(`Chat input action is not available: ${action}`);
    }
};

const createCopyCodeBlockHost = (page: ChatActionHandlerDependencies): CopyCodeBlockHost => {
    return {
        feedback: page.page.feedback,
        hasClipboardSupport: () => page.page.services.hasClipboardSupport(),
        copyToClipboard: (text, copyOptions) => page.page.services.copyToClipboard(text, copyOptions)
    };
};

const createCopyInlineMediaReferenceHost = (page: ChatActionHandlerDependencies): CopyInlineMediaReferenceHost => {
    return {
        feedback: page.page.feedback,
        hasClipboardSupport: () => page.page.services.hasClipboardSupport(),
        copyToClipboard: (text, copyOptions) => page.page.services.copyToClipboard(text, copyOptions)
    };
};

const createAgentPlanExecutionHost = (page: ChatActionHandlerDependencies): AgentPlanExecutionHost => {
    return {
        feedback: page.page.feedback,
        getCurrentConversationId: () => page.state.conversationState.currentConversationId,
        isConversationExecuting: (conversationId) => page.state.conversationView.isExecuting(conversationId),
        resolveModeForConversation: (conversationId) => page.runtime.turnRuntime.requireAgent().resolveModeForConversation(conversationId),
        selectMode: (mode) => page.runtime.turnRuntime.requireAgent().handleModeSelect(mode),
        waitForPendingModeUpdate: () => page.runtime.turnRuntime.requireAgent().waitForPendingModeUpdate(),
        sendTextMessage: (text) => page.sessions.messageSending.sendTextMessage(text)
    };
};

const createOpenInlineMediaLocalFolderHost = (page: ChatActionHandlerDependencies): OpenInlineMediaLocalFolderHost => {
    return {
        navigateWithQuery: (targetPage, query) => page.platform.router.navigateWithQuery(targetPage, query)
    };
};

const openComposerAttachmentOverflow = (page: ChatActionHandlerDependencies): void => {
    const conversationId = page.state.conversationState.currentConversationId;
    if (!isString(conversationId) || !conversationId.trim()) {
        throw new Error('Composer attachment overflow requires a conversation id');
    }
    const records = buildDraftAttachmentOverflowRecords({
        conversationId: conversationId.trim(),
        attachments: page.runtime.composerSurface.requireAttachments().getAttachments(),
        knowledgeDrafts: page.sessions.messageSending.rag.currentKnowledgeDrafts(),
        ingestionStatus: page.sessions.messageSending.rag.currentStatus()
    });
    if (records.length === 0) {
        return;
    }
    page.runtime.conversationRuntime.requireMessages().showAttachmentOverflowRecords(conversationId.trim(), records);
};

const composeChatActionHandlerRuntime = (page: ChatActionHandlerDependencies): ChatActionHandlersHost => {
    return {
        shared: { pageResources: page.page.pageResources, feedback: page.page.feedback, api: page.platform.api },
        navigation: {
            navigate: (targetPage) => runNavigationOperation(`chat:navigate:${targetPage}`, () => page.platform.router.navigate(targetPage)),
            navigateWithQuery: (targetPage, query) => runNavigationOperation(`chat:navigateWithQuery:${targetPage}`, () => page.platform.router.navigateWithQuery(targetPage, query))
        },
        conversation: {
            actions: page.sessions.conversationActions,
            currentModel: () => page.state.conversationState.currentModel,
            current: () => page.state.conversationView.current(),
            currentId: () => page.state.conversationState.currentConversationId,
            export: (conversationId) => page.sessions.messageSending.exportConversation(conversationId),
            updateWorkspacePath: (conversationId, config) => page.state.preferences.updateWorkspacePath(conversationId, config),
            isStreaming: (conversationId) => page.state.conversationView.isStreaming(conversationId),
            isExecuting: (conversationId) => page.state.conversationView.isExecuting(conversationId),
            requireId: (actionElement, ancestorSelector) => page.callbacks.requireConversationIdFromElement(actionElement, ancestorSelector),
            openEnsuringLoaded: (conversationId) => page.state.conversationView.openEnsuringLoaded(conversationId),
            refreshSidebar: () => page.state.conversationView.refreshSidebar()
        },
        execution: {
            canQueue: (conversationId) => page.runtime.turnRuntime.requireStreaming().canQueueConversationInput(conversationId),
            admission: (conversationId) => page.runtime.turnRuntime.requireStreaming().getCachedTurnAdmission(conversationId),
            syncAdmission: (conversationId) => page.runtime.turnRuntime.requireStreaming().resolveSyncedTurnAdmission(conversationId, page.page.pageLifecycle.signal()),
            stop: (options) => page.runtime.turnRuntime.requireStreaming().stopStreaming(options),
            waitForRequestExit: (conversationId, requestId) => page.runtime.turnRuntime.requireStreaming().waitForConversationRequestExit(conversationId, requestId, page.page.pageLifecycle.signal()),
            run: (operationId, task) => page.sessions.taskScope.run(operationId, task),
            boundary: <T>(name: string, functionValue: () => Promise<T>) => page.page.pageLifecycle.run(name, functionValue),
            send: (options) => page.sessions.messageSending.sendMessage(options),
            steer: () => page.sessions.messageSending.steerActiveStream(),
            queue: (intent) => page.sessions.messageSending.queueConversationInputFromComposer(intent)
        },
        composer: {
            cycleTokenCounter: () => page.sessions.composer.cycleTokenCounter(),
            requireInput: () => requireChatInput(page),
            setInput: (input, value) => {
                page.page.pageElements.setValue(input, value, { attribute: 'value' });
                page.sessions.composer.noteDraftChanged(value);
            },
            cancelConversationInput: (conversationId, inputId) => page.sessions.composer.cancelConversationInput(conversationId, inputId),
            resolveAskUser: (conversationId, taskId, action) => page.sessions.composer.resolveAskUserPrompt(conversationId, taskId, action),
            resolveSecret: (conversationId, taskId, payload) => page.sessions.composer.resolveSecretPrompt(conversationId, taskId, payload),
            resolveToolApproval: (conversationId, taskId, action) => page.sessions.composer.resolveToolApprovalPrompt(conversationId, taskId, action),
            toggleCall: () => {
                requireInputActionEnabled('call', page.state.settings.parameters.inputActionCallEnabled === true);
                page.sessions.composer.toggleCall();
            },
            toggleTools: () => page.sessions.composer.toggleTools(),
            openAttachmentOverflow: () => openComposerAttachmentOverflow(page),
            openCharacterMap: () => {
                if (page.state.settings.parameters.inputActionCharacterMapEnabled !== true) throw new Error('Chat character-map action is not available');
                page.sessions.characterMapSession.open();
            },
            updateInputState: () => page.runtime.composerSurface.requireUi().updateInputState(),
            applyInputActionVisibility: () => page.sessions.composer.applyInputActionVisibility(),
            updateInputQueuePreview: () => page.runtime.composerSurface.requireUi().updateInputQueuePreview(),
            resolvePrimaryActionMode: () => page.runtime.composerSurface.requireUi().resolveComposerActionMode()
        },
        attachments: {
            fileUploadEnabled: () => page.state.settings.parameters.inputActionFileUploadEnabled === true,
            cameraEnabled: () => page.state.settings.parameters.inputActionCameraEnabled === true,
            drafts: () => page.runtime.composerSurface.requireAttachments().getAttachments(),
            draftCommitEpoch: () => page.runtime.composerSurface.requireAttachments().getDraftCommitEpoch(),
            subscribeDrafts: (handler) => page.runtime.composerSurface.requireAttachments().subscribeDraftChanges(handler),
            requireFileInput: () => requireUploadInput(page, '.file-upload-input', 'Chat file upload input'),
            requireFolderInput: () => requireUploadInput(page, '.folder-upload-input', 'Chat folder upload input'),
            uploadFiles: (files) => {
                requireInputActionEnabled('fileUpload', page.state.settings.parameters.inputActionFileUploadEnabled === true);
                return page.sessions.messageSending.handleSelectedUploadFiles(files);
            },
            uploadFolder: (files) => {
                requireInputActionEnabled('fileUpload', page.state.settings.parameters.inputActionFileUploadEnabled === true);
                return page.sessions.messageSending.handleSelectedFolderUploadFiles(files);
            },
            captureCamera: (file) => {
                requireInputActionEnabled('camera', page.state.settings.parameters.inputActionCameraEnabled === true);
                return page.sessions.messageSending.handleCameraCaptureFile(file);
            },
            addSoaiPaths: (records) => page.runtime.composerSurface.requireAttachments().addResolvedSoaiPathRecords(records),
            removeFile: (fileId) => page.sessions.messageSending.removeAttachedFile(fileId),
            removeKnowledge: (knowledgeAttachmentId) => page.sessions.messageSending.removeDraftKnowledgeAttachment(knowledgeAttachmentId)
        },
        audio: {
            toggleRecording: () => {
                requireInputActionEnabled('voice', page.state.settings.parameters.inputActionVoiceEnabled === true);
                page.sessions.voiceSession.toggleRecording();
            },
            cancelRecording: () => page.sessions.voiceSession.cancelRecording()
        },
        configuration: {
            toggle: () => page.runtime.composerSurface.requireUi().toggleConfiguration(),
            openTab: (tabId) => page.sessions.configurationSession.openTab(tabId),
            openMemoryProfile: () => page.sessions.configurationSession.openMemoryProfile(),
            refreshMemory: () => page.sessions.configurationSession.refreshMemoryTabFromAction(),
            handleModelAction: (actionElement) => page.sessions.configurationSession.handleModelAction(actionElement),
            refreshPresets: () => page.sessions.configurationSession.refreshPresets(),
            resetPresets: () => page.sessions.configurationSession.resetPresets(),
            newPreset: () => page.sessions.configurationSession.newPreset(),
            applyPreset: (actionElement) => page.sessions.configurationSession.applyPreset(actionElement),
            replacePreset: (actionElement) => page.sessions.configurationSession.replacePreset(actionElement),
            renamePreset: (actionElement) => page.sessions.configurationSession.renamePreset(actionElement),
            removePreset: (actionElement) => page.sessions.configurationSession.removePreset(actionElement),
            submitPresetEditor: () => page.sessions.configurationSession.submitPresetEditor(),
            cancelPresetEditor: () => page.sessions.configurationSession.cancelPresetEditor(),
            reviewPresetEditor: () => page.sessions.configurationSession.reviewPresetEditor(),
            restoreDefaults: () => page.runtime.configurationRuntime.requireParameters().restoreDefaults(),
            save: () => page.state.preferences.saveConfiguration(),
            openToolOutput: (inputArguments) => page.sessions.configurationSession.openToolCallOutput(inputArguments)
        },
        presentation: {
            toggleFavoritesAtTop: () => toggleFavoritesAtTop(page.sessions.uiBehaviors),
            toggleSidebar: () => page.runtime.composerSurface.requireUi().toggleSidebar(),
            actionData: (actionElement, key) => {
                const value = page.platform.dom.getData(actionElement, key);
                return isString(value) ? value : null;
            },
            showColorPicker: (actionElement, conversationId) => page.sessions.presentation.showConversationColorPicker(actionElement, conversationId),
            activeColorPickerConversationId: () => page.state.viewState.activeColorPickerConversationId,
            hideColorPicker: () => page.sessions.presentation.hideConversationColorPicker(),
            hasClipboardSupport: () => page.page.services.hasClipboardSupport(),
            copyToClipboard: (text, options) => page.page.services.copyToClipboard(text, options),
            copyCodeBlock: (actionElement) => copyCodeBlock(createCopyCodeBlockHost(page), actionElement),
            copyInlineMediaReference: (actionElement) => copyInlineMediaReference(createCopyInlineMediaReferenceHost(page), actionElement),
            openInlineMediaLocalFolder: (actionElement) => openInlineMediaLocalFolder(createOpenInlineMediaLocalFolderHost(page), actionElement),
            dispatchMessageAction: (actionElement, action, event) => page.callbacks.dispatchMessageAction(actionElement, action, event),
            handleComparisonNavigation: (actionElement) => page.state.modelSession.handleComparisonNavigation(actionElement),
            handleModelControlAction: (actionElement) => page.state.modelSession.handleControlAction(actionElement),
            uploadAssistantAvatar: () => page.sessions.avatar.uploadAssistant(),
            removeAssistantAvatar: () => page.sessions.avatar.removeAssistant(),
            uploadUserAvatar: () => page.sessions.avatar.uploadUser(),
            removeUserAvatar: () => page.sessions.avatar.removeUser(),
            toggleToolActivityItem: (actionElement) => page.runtime.composerSurface.requireUi().toggleToolActivityItem(actionElement)
        },
        agent: {
            cycleMode: () => page.runtime.turnRuntime.requireAgent().handleModeCycle(),
            compact: () => page.runtime.turnRuntime.requireAgent().handleCompact(),
            toggleTodoPanel: () => page.runtime.turnRuntime.requireAgent().handleToggleTodoPanel(),
            togglePlanBar: () => page.runtime.turnRuntime.requireAgent().handleTogglePlanBar(),
            viewPlan: () => page.runtime.turnRuntime.requireAgent().handleViewAgentPlan(),
            executePlan: () => startAgentPlanExecution(createAgentPlanExecutionHost(page))
        },
        toolbar: {
            toggle: () => page.sessions.conversationToolbarSession.toggleExpanded(),
            enterSelectMode: () => page.sessions.conversationToolbarSession.enterSelectMode(),
            exitSelectMode: () => page.sessions.conversationToolbarSession.exitSelectMode(),
            deleteSelected: () => page.sessions.conversationToolbarSession.executeBatchDelete(),
            cloneSelected: () => page.sessions.conversationToolbarSession.executeBatchClone(),
            archiveSelected: () => page.sessions.conversationToolbarSession.executeBatchArchive(),
            openArchived: () => page.sessions.conversationToolbarSession.openArchivedConversations(),
            openPrompts: () => page.sessions.promptPickerSession.open(),
            selectionActive: () => page.sessions.conversationToolbarSession.isSelectionActive(),
            toggleSelection: (conversationId) => page.sessions.conversationToolbarSession.toggleConversationSelection(conversationId)
        },
        rag: {
            cancel: () => page.sessions.messageSending.rag.cancelCurrent(),
            status: (conversationId) => page.sessions.messageSending.rag.statusForConversation(conversationId),
            subscribe: (handler) => page.sessions.messageSending.rag.subscribeStatus(handler),
            start: (inputArguments) => page.sessions.messageSending.rag.start(inputArguments),
            handleKnowledgeChanged: (summary) => page.sessions.messageSending.rag.handleKnowledgeChanged(summary),
            cancelForConversation: (conversationId) => page.sessions.messageSending.rag.cancel(conversationId)
        }
    };
};

interface ChatPageActionRuntime {
    host: ChatActionHandlersHost;
    handlers: Record<ChatActionId, (actionElement: HTMLElement, event: Event) => void>;
}

const createChatPageActionRuntime = (page: ChatActionHandlerDependencies): ChatPageActionRuntime => {
    const host = composeChatActionHandlerRuntime(page);
    return { host, handlers: createChatActionHandlers(host) };
};

export { composeChatActionHandlerRuntime, createChatPageActionRuntime };
export type { ChatPageActionRuntime };
