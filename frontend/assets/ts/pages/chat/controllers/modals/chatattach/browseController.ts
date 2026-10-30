/* SoAI - Chat workspace and Knowledge sources for the shared attachment browser [frontend/assets/ts/pages/chat/controllers/modals/chatattach/browseController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseFileBrowserLoadResponse } from '@core/fileexplorerbrowser/parsing.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import { AttachBrowseController, type AttachBrowseElements, type AttachBrowseSearchOutcome } from '@features/attachmodal/public.ts';
import { captureSoaiLinkWorkspaceSnapshot, matchesSoaiLinkWorkspaceSnapshot } from '@features/chat/public.ts';
import type { ChatAttachBrowseHost } from '@pages/chat/controllers/modals/chatattach/contracts.ts';
import { ChatAttachBrowseWorkspacePathController } from '@pages/chat/controllers/modals/chatattach/ChatAttachBrowseWorkspacePathController.ts';
import { ChatAttachBrowseKnowledgeOperations } from '@pages/chat/controllers/modals/chatattach/chatAttachBrowseKnowledgeController.ts';
import { ChatAttachBrowseWorkspaceOperations } from '@pages/chat/controllers/modals/chatattach/chatAttachBrowseWorkspaceController.ts';
import { buildWorkspaceBrowseResults, parseReusableKnowledgeResults, type ChatAttachBrowseResult } from '@pages/chat/controllers/modals/chatattach/chatAttachBrowseResultsWidget.ts';
import { createChatAttachDraftList } from '@pages/chat/controllers/modals/chatattach/chatAttachDraftListController.ts';

const BROWSE_RESULT_LIMIT = 20;

const createChatAttachBrowseController = (host: ChatAttachBrowseHost, elements: AttachBrowseElements, signal: AbortSignal): AttachBrowseController<ChatAttachBrowseResult> => {
    const knowledge = new ChatAttachBrowseKnowledgeOperations(host, signal);
    const workspace = new ChatAttachBrowseWorkspaceOperations(host, signal);
    const workspacePath = new ChatAttachBrowseWorkspacePathController(host, elements, async (): Promise<void> => {
        browse.handleInput();
    });
    const browse: AttachBrowseController<ChatAttachBrowseResult> = new AttachBrowseController<ChatAttachBrowseResult>(
        {
            hasOwner: () => toTrimmedStringOrNull(host.conversation.currentId()) !== null,
            captureScope: () => host.attachments.captureIntake().scope,
            captureSearch: () => {
                const conversation = host.conversation.current();
                const conversationId = toTrimmedStringOrNull(conversation?.id);
                const snapshot = captureSoaiLinkWorkspaceSnapshot(conversation);
                const intake = host.attachments.captureIntake();
                return {
                    search: async (query, requestSignal): Promise<AttachBrowseSearchOutcome<ChatAttachBrowseResult>> => {
                        if (conversationId === null) return { type: 'no-owner' };
                        if (!intake.scope.isCurrent()) return { type: 'superseded', refresh: false };
                        const [workspacePayload, knowledgePayload] = await Promise.all([host.shared.api.webui.chat.soaiPaths.browse(conversationId, { query: query || null, limit: BROWSE_RESULT_LIMIT }, { signal: requestSignal }), host.shared.api.webui.chat.attachments.knowledge.reusable({ query: query || undefined, limit: BROWSE_RESULT_LIMIT, signal: requestSignal })]);
                        if (requestSignal.aborted) return { type: 'superseded', refresh: false };
                        if (!matchesSoaiLinkWorkspaceSnapshot(host.conversation.current(), snapshot)) return { type: 'superseded', refresh: true };
                        if (!intake.scope.isCurrent()) return { type: 'superseded', refresh: false };
                        return { type: 'ready', results: [...buildWorkspaceBrowseResults(parseFileBrowserLoadResponse(workspacePayload, query).entries), ...parseReusableKnowledgeResults(knowledgePayload)] };
                    }
                };
            },
            activateWorkspace: () => workspacePath.activate(),
            deactivateWorkspace: () => workspacePath.deactivate(),
            openWorkspacePathPicker: () => workspacePath.openPicker(host.attachments.captureIntake().scope),
            preview: (result, isCurrent) => (result.type === 'workspace' ? workspace.preview(result, isCurrent) : knowledge.preview(result, isCurrent)),
            attach: (result, isCurrent) => (result.type === 'workspace' ? workspace.attach(result, isCurrent) : knowledge.attach(result, isCurrent)),
            abortActions: () => {
                workspace.abortPending();
                knowledge.abortPending();
            },
            run: (operation, task) => host.execution.run(operation, task)
        },
        elements,
        signal,
        createChatAttachDraftList(host, elements.draftList, signal, 'browse')
    );
    return browse;
};

export { createChatAttachBrowseController };
