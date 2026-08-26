/* SoAI - Chat composer SoAI link input resolution [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/soaiLinkInputController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { runWithAbortSignalScope } from '@core/errors/abort.ts';
import { i18n } from '@core/i18n/index.ts';
import { containsSoaiPathToken } from '@core/soailinks/codec.ts';
import { isString } from '@core/typeGuards.ts';
import { captureSoaiLinkWorkspaceSnapshot, matchesSoaiLinkWorkspaceSnapshot, requireMatchingResolveRecords } from '@features/chat/public.ts';
import { resolveSoaiLinkDraftRecordsWithNotification } from '@pages/chat/controllers/soaiLinkResolveController.ts';
import type { MessageSendingHost } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';

const resolveComposerSoaiLinksFromInput = async (host: MessageSendingHost, input: HTMLTextAreaElement, inputValue: string): Promise<void> => {
    if (!containsSoaiPathToken(inputValue)) {
        return;
    }
    const conversation = await host.platform.ensureConversationForSend();
    if (conversation === null) {
        return;
    }
    const attachmentManager = host.services.getAttachmentManager();
    const draftRevision = attachmentManager.getDraftRevision();
    const resolutionManager = host.services.getSoaiLinkResolutionManager();
    const requestSeq = resolutionManager.nextInputResolveSeq();
    const workspaceSnapshot = captureSoaiLinkWorkspaceSnapshot(host.conversation.getCurrentConversation());
    await runWithAbortSignalScope([host.platform.getRuntimeAbortSignal()], async (signal) => {
        const response = await resolveSoaiLinkDraftRecordsWithNotification({
            api: host.services.getChatApi(),
            conversationId: conversation.conversationId,
            rawText: inputValue,
            signal,
            boundaryName: 'chat:resolveInputSoaiLinks'
        });
        if (response === null) {
            return;
        }
        const records = requireMatchingResolveRecords(response, inputValue);
        if (records.length === 0 || signal.aborted || !resolutionManager.isInputResolveSeqCurrent(requestSeq) || input.value !== inputValue || host.conversation.getCurrentConversation()?.id !== conversation.conversationId || !matchesSoaiLinkWorkspaceSnapshot(host.conversation.getCurrentConversation(), workspaceSnapshot) || attachmentManager.getDraftRevision() !== draftRevision) {
            return;
        }
        const nextValue = resolutionManager.commitResolvedSource(inputValue, records);
        host.composer.setUIValue(input, nextValue, { attribute: 'value' });
        const addedCount = attachmentManager.addResolvedSoaiPathRecords(records);
        host.composer.resizeChatInput(input);
        host.composer.noteChatInputDraftChanged(nextValue);
        if (addedCount > 0) {
            host.platform.feedback.show(i18n.plural('chat.attachments.soaiPathLinkAdded', addedCount, { count: addedCount }), 'success');
            host.composer.updateInputState();
        }
    });
};

const hasInputSoaiPathToken = (value: string): boolean => {
    return isString(value) && containsSoaiPathToken(value);
};

export { hasInputSoaiPathToken, resolveComposerSoaiLinksFromInput };
