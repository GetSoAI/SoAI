/* SoAI - Chat workspace link acceptance for the shared dialog [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachLinkController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { AttachLinkController, type AttachLinkElements } from '@features/attachmodal/public.ts';
import { captureSoaiLinkWorkspaceSnapshot, matchesSoaiLinkWorkspaceSnapshot, requireMatchingResolveRecords } from '@features/chat/public.ts';
import type { ChatAttachSoaiLinkHost } from '@pages/chat/controllers/modals/chatattach/contracts.ts';
import { createChatAttachDraftList } from '@pages/chat/controllers/modals/chatattach/chatAttachDraftListController.ts';
import { resolveSoaiLinkDraftRecordsWithNotification } from '@pages/chat/controllers/soaiLinkResolveController.ts';

const createChatAttachLinkController = (host: ChatAttachSoaiLinkHost, elements: AttachLinkElements, signal: AbortSignal): AttachLinkController =>
    new AttachLinkController(
        {
            captureLookup: () => {
                const intake = host.attachments.captureIntake();
                return async (value, lookupSignal, isCurrent) => {
                    if (!intake.scope.isCurrent() || !isCurrent()) return false;
                    const conversationId = await intake.acceptConversation();
                    if (conversationId === null || !intake.scope.isCurrent() || !isCurrent()) return false;
                    const workspace = captureSoaiLinkWorkspaceSnapshot(host.conversation.current());
                    const response = await resolveSoaiLinkDraftRecordsWithNotification({ api: host.shared.api, conversationId, rawText: value, signal: lookupSignal, boundaryName: 'chat:attachModalResolveSoaiLinks' });
                    if (response === null || !isCurrent() || !intake.scope.isCurrent() || !matchesSoaiLinkWorkspaceSnapshot(host.conversation.current(), workspace)) return false;
                    const records = requireMatchingResolveRecords(response, value);
                    const count = host.attachments.addSoaiPaths(records, 'soaiLink');
                    if (count > 0) host.shared.feedback.show(i18n.plural('chat.attachments.soaiPathLinkAdded', count, { count }), 'success');
                    return true;
                };
            },
            run: (task) => host.execution.run('chat:attachModalSoaiLinkResolve', task)
        },
        elements,
        signal,
        createChatAttachDraftList(host, elements.draftList, signal, 'soaiLink')
    );

export { createChatAttachLinkController };
