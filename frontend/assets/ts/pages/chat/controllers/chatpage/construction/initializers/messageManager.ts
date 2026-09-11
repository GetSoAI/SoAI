/* SoAI - Chat page message manager initialization [frontend/assets/ts/pages/chat/controllers/chatpage/construction/initializers/messageManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutViewport } from '@core/layout/elementGeometry.ts';
import { resolveModelTypeLabel } from '@core/models/modelTypeLabel.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import { CHAT_ACTIVITY_COMPACT_BREAKPOINT_PX, CHAT_SELECTORS, ChatMessageManager, normalizeConversationId, resolveActivityDurationDisplayMode, type ChatMessageManagerDependencies } from '@features/chat/public.ts';
import type { ChatControllerInitializationContext } from '@pages/chat/controllers/chatpage/construction/initializers/contracts.ts';
import { updateConversationRenderCacheEntry } from '@pages/chat/controllers/page/renderer/currentConversationStateController.ts';
import { isThinkingFeatureEnabled } from '@pages/chat/controllers/page/state.ts';
import { resolveVoiceTtsSettings } from '@pages/chat/controllers/voice/service.ts';

const initializeMessageManager = (page: ChatControllerInitializationContext): void => {
    if (page.runtime.conversationRuntime.hasMessages()) {
        return;
    }
    const modelAvailability = page.state.conversationState.modelAvailability;
    if (!modelAvailability) {
        throw new Error('ChatPage requires model availability state');
    }
    const messageManagerDependencies: ChatMessageManagerDependencies = {
        boundary: {
            apiClient: {
                request: (method, endpoint, body, options) => page.platform.api.request(method, endpoint, body, options)
            },
            knowledgeAttachmentsApi: {
                items: (conversationId, knowledgeAttachmentId, options) => page.platform.api.webui.chat.attachments.knowledge.items(conversationId, knowledgeAttachmentId, options),
                delete: (conversationId, knowledgeAttachmentId, options) => page.platform.api.webui.chat.attachments.knowledge.delete(conversationId, knowledgeAttachmentId, options),
                previewItem: (conversationId, knowledgeAttachmentId, itemId, payload, options) => page.platform.api.webui.chat.attachments.knowledge.previewItem(conversationId, knowledgeAttachmentId, itemId, payload, options),
                useItems: (conversationId, payload, options) => page.platform.api.webui.chat.attachments.knowledge.useItems(conversationId, payload, options)
            },
            soaiPathsApi: {
                preview: (conversationId, payload, options) => page.platform.api.webui.chat.soaiPaths.preview(conversationId, payload, options),
                read: (conversationId, payload, options) => page.platform.api.webui.chat.soaiPaths.read(conversationId, payload, options),
                download: (conversationId, payload, options) => page.platform.api.webui.chat.soaiPaths.download(conversationId, payload, options),
                open: (conversationId, payload, options) => page.platform.api.webui.chat.soaiPaths.open(conversationId, payload, options),
                token: (conversationId, payload, options) => page.platform.api.webui.chat.soaiPaths.token(conversationId, payload, options)
            }
        },
        presentation: {
            sanitizer: page.platform.pageContext.sanitizer,
            chatToolIconService: page.state.runtimeServices.toolIcons,
            getCachedIcon: (name, options) => page.sessions.presentation.cachedIcon(name, options),
            getMessageSenderLabel: (source, defaultRole) => page.sessions.modelSession.messageSenderLabel(source, defaultRole),
            getModelTypeLabel: (modelId) => resolveModelTypeLabel(modelId ? (page.state.conversationState.modelIndex.get(modelId) ?? null) : null),
            isThinkingFeatureEnabled,
            isRichTextEnabled: () => page.state.settings.richTextEnabled(),
            isCodeRecognitionEnabled: () => page.state.settings.storage.getCodeRecognitionEnabled(),
            isInlineMultimediaPreviewsEnabled: () => page.state.settings.inlineMultimediaPreviewsEnabled(),
            isShowActivitiesEnabled: () => page.state.settings.showActivitiesEnabled(),
            getActivityDurationDisplayMode: () => resolveActivityDurationDisplayMode(measureLayoutViewport(page.platform.dom.getDocument()).width, CHAT_ACTIVITY_COMPACT_BREAKPOINT_PX),
            dom: { getDocument: () => page.platform.dom.getDocument() },
            getAssistantAvatarUrl: () => page.state.settings.storage.getAssistantAvatar(),
            getUserAvatarUrl: () => page.state.settings.storage.getUserAvatar()
        },
        session: {
            getCurrentModel: () => toTrimmedStringOrNull(page.state.conversationState.currentModel),
            getModelStreamHasPayload: () => modelAvailability.getModelStreamHasPayload(),
            isModelAvailable: (modelId) => modelAvailability.isModelAvailable(modelId),
            isTerminalRenderPending: (conversationId, message) => {
                const normalizedConversationId = normalizeConversationId(conversationId);
                if (!normalizedConversationId || !page.runtime.turnRuntime.hasStreaming()) {
                    return false;
                }
                return page.runtime.turnRuntime.requireStreaming().isTerminalRenderPending(normalizedConversationId, message);
            },
            isConversationExecuting: (conversationId) => page.sessions.conversationView.isExecuting(conversationId),
            getActiveComparisonRun: (conversationId) => {
                const normalizedConversationId = normalizeConversationId(conversationId);
                if (!normalizedConversationId || !page.runtime.turnRuntime.hasStreaming()) {
                    return null;
                }
                return page.runtime.turnRuntime.requireStreaming().getActiveComparisonRun(normalizedConversationId);
            },
            getActiveStreamIdentity: (conversationId) => {
                const normalizedConversationId = normalizeConversationId(conversationId);
                if (!normalizedConversationId || !page.runtime.turnRuntime.hasStreaming()) {
                    return null;
                }
                return page.runtime.turnRuntime.requireStreaming().getStreamIdentity(normalizedConversationId);
            },
            getCanonicalPlan: () => page.runtime.turnRuntime.optionalAgent()?.getCanonicalPlan() ?? null,
            getCurrentConversation: () => page.sessions.conversationView.current(),
            getCurrentRunningActivitySnapshot: () => page.sessions.conversationView.current()?.history?.runningActivity ?? null,
            resolveConversationById: (conversationId) => page.state.conversationState.conversations.get(conversationId) ?? null
        },
        runtime: {
            saveAndSync: async (conversation) => {
                if (!page.runtime.conversationRuntime.hasStorage()) {
                    throw new Error('ChatMessageManager requires a storage manager');
                }
                await page.runtime.conversationRuntime.requireStorage().saveAndSync(conversation);
            },
            resubmitUserMessage: async (conversation, inputArguments) => {
                if (!page.runtime.conversationRuntime.hasStorage()) {
                    throw new Error('ChatMessageManager requires a storage manager');
                }
                await page.runtime.conversationRuntime.requireStorage().resubmitUserMessage(conversation, inputArguments);
            },
            truncateMessagesFromCursor: async (conversation, inputArguments) => {
                if (!page.runtime.conversationRuntime.hasStorage()) {
                    throw new Error('ChatMessageManager requires a storage manager');
                }
                await page.runtime.conversationRuntime.requireStorage().truncateMessagesFromCursor(conversation, inputArguments);
            },
            deleteMessageByCursor: async (conversation, inputArguments) => {
                if (!page.runtime.conversationRuntime.hasStorage()) {
                    throw new Error('ChatMessageManager requires a storage manager');
                }
                await page.runtime.conversationRuntime.requireStorage().deleteMessageByCursor(conversation, inputArguments);
            },
            loadConversationMessages: async (conversationId, options) => {
                if (!page.runtime.conversationRuntime.hasStorage()) {
                    throw new Error('ChatMessageManager requires a storage manager');
                }
                await page.runtime.conversationRuntime.requireStorage().loadConversationMessages(conversationId, options);
            },
            refreshRunningActivitySnapshot: async (conversationId) => {
                if (!page.runtime.conversationRuntime.hasStorage()) {
                    throw new Error('ChatMessageManager requires a storage manager');
                }
                await page.runtime.conversationRuntime.requireStorage().refreshRunningActivitySnapshot(conversationId);
            },
            streamResponse: async (conversation, options) => {
                if (!page.runtime.turnRuntime.hasStreaming()) {
                    throw new Error('ChatMessageManager requires a streaming controller');
                }
                await page.runtime.turnRuntime.requireStreaming().streamResponse(conversation, options);
            },
            commitPendingDeletesForConversation: async (conversation) => {
                await page.runtime.conversationRuntime.requireMessages().commitPendingDeletesForConversation(conversation);
            },
            runConversationExecutionIfIdle: async (conversationId, task) => await page.sessions.messageSending.runConversationExecutionIfIdle(conversationId, task),
            invalidateChatMarkup: (scope) => page.sessions.conversationView.invalidate(scope),
            renderCurrentConversation: () => page.sessions.conversationView.renderCurrent(),
            renderConversationList: () => page.sessions.conversationView.renderList(),
            refreshConversationsUI: () => page.sessions.conversationView.refresh(),
            regenerateCompactionInCurrentConversation: async (assistantTurnAtMs) => {
                const agentService = page.runtime.turnRuntime.optionalAgent();
                if (!agentService) {
                    throw new Error('ChatMessageManager requires an agent service for compaction regeneration');
                }
                const normalizedConversationId = normalizeConversationId(page.state.conversationState.currentConversationId);
                if (!normalizedConversationId) {
                    return;
                }
                await page.sessions.messageSending.runConversationExecutionIfIdle(normalizedConversationId, async () => {
                    await agentService.handleRegenerateCompaction(assistantTurnAtMs);
                });
            },
            removeCompactionBoundary: async (payload) => {
                const normalizedConversationId = normalizeConversationId(payload.conversationId);
                if (!normalizedConversationId) {
                    throw new Error('Context compaction boundary removal requires a conversation id');
                }
                await page.platform.api.webui.chat.agent.removeCompactionBoundary(normalizedConversationId, {
                    assistantTurnAtMs: payload.assistantTurnAtMs,
                    modelVariantIndex: payload.modelVariantIndex,
                    toolCallId: payload.toolCallId,
                    expectedLastModifiedAtMs: payload.expectedLastModifiedAtMs
                });
            },
            stopShell: async (payload) => {
                const normalizedConversationId = normalizeConversationId(payload.conversationId);
                if (!normalizedConversationId) {
                    throw new Error('Shell stop requires a conversation id');
                }
                return await page.platform.api.webui.chat.agent.stopShellToolCall(normalizedConversationId, {
                    assistantTurnAtMs: payload.assistantTurnAtMs,
                    modelVariantIndex: payload.modelVariantIndex,
                    toolCallId: payload.toolCallId
                });
            },
            isConversationExecuting: (conversationId) => page.sessions.conversationView.isExecuting(conversationId),
            isChatStreamingConversation: (conversationId) => {
                const normalizedConversationId = normalizeConversationId(conversationId);
                return normalizedConversationId ? page.sessions.conversationView.isStreaming(normalizedConversationId) : false;
            },
            reportRequestFailure: (error) => page.sessions.conversationView.reportFailure(error),
            speakText: async (text, options) => {
                const settings = resolveVoiceTtsSettings(page.state.settings.parameters);
                await page.sessions.voiceSession.speakText(text, {
                    model: settings.model,
                    voice: settings.voice,
                    responseFormat: 'wav',
                    speed: settings.speed,
                    onPlaybackStart: options?.onPlaybackStart ?? null
                });
            },
            stopSpeaking: () => {
                page.sessions.voiceSession.stopSpeaking();
            }
        },
        rendering: {
            getAttachmentDraftRevision: () => {
                const attachmentManager = page.runtime.composerSurface.optionalAttachments();
                if (attachmentManager === null) {
                    throw new Error('ChatMessageManager requires an attachment manager');
                }
                return attachmentManager.getDraftRevision();
            },
            getWorkerRenderEpoch: () => page.sessions.taskScope.concurrency.getWorkerRenderEpoch(),
            invalidateActiveStreamDomCache: (conversationId, messageDomId) => {
                if (page.runtime.turnRuntime.hasStreaming()) {
                    page.runtime.turnRuntime.requireStreaming().invalidateMessageDomCache(conversationId, messageDomId);
                }
            },
            updateConversationRenderCache: (conversationId, messageDomId, signature) => updateConversationRenderCacheEntry({ cache: page.state.viewState.conversationRenderCache, conversationId, messageDomId, signature }),
            revealActivityElement: (element) => {
                page.runtime.composerSurface.requireUi().revealElementFromUserAction(element, { behavior: 'smooth', block: 'center', inline: 'nearest' });
            }
        },
        interaction: {
            runWithBoundary: (name, functionValue) => page.page.pageLifecycle.run(name, functionValue),
            handleError: (error, context, options) => page.page.feedback.handle(error, context, options),
            hasClipboardSupport: () => page.page.services.hasClipboardSupport(),
            copyToClipboard: (text, options) => page.page.services.copyToClipboard(text, options),
            showNotification: (message, type) => page.page.feedback.show(message, type),
            onKnowledgeAttachmentChanged: (summary) => {
                page.sessions.messageSending.rag.handleKnowledgeChanged(summary);
            },
            notifyConversationContentCommitted: () => {
                if (page.page.pageDom.query(CHAT_SELECTORS.TOKEN_COUNTER_BTN).length > 0) {
                    page.sessions.composer.noteConversationContentCommitted();
                }
            }
        }
    };
    page.runtime.conversationRuntime.initializeMessages(new ChatMessageManager(messageManagerDependencies, page.state.runtimeServices.syntaxHighlighter));
};

export { initializeMessageManager };
