/* SoAI - Chat composer SoAI link payload controller [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/soaiLinkPayloadController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { runWithAbortSignalScope } from '@core/errors/abort.ts';
import type { SoaiLinkResolveResponse } from '@core/api/contracts/webuiChatOperationContracts.ts';
import { containsSoaiPathToken, stripSoaiPathTokensForDisplay } from '@core/soailinks/codec.ts';
import { isPlainObject, isString } from '@core/typeGuards.ts';
import { captureSoaiLinkWorkspaceSnapshot, matchesSoaiLinkWorkspaceSnapshot, requireMatchingResolveContentParts, type ChatContentSegment, type Conversation } from '@features/chat/public.ts';
import type { ComposerSoaiLinkResolutionManager } from '@pages/chat/controllers/chatmessagesendingcontroller/composerSoaiLinkResolutionManager.ts';
import type { ComposerPayload } from '@pages/chat/controllers/chatmessagesendingcontroller/effects.ts';

type SoaiLinkResolveSnapshot = { type: 'composer'; requestSeq: number; messageText: string; workspaceSnapshot: ReturnType<typeof captureSoaiLinkWorkspaceSnapshot> } | { type: 'payload'; requestSeq: number; workspaceSnapshot: ReturnType<typeof captureSoaiLinkWorkspaceSnapshot> };
interface SoaiLinkPayloadResolveHost {
    platform: {
        runWithBoundary: <T>(name: string, functionValue: () => Promise<T>) => Promise<T>;
        getRuntimeAbortSignal: () => AbortSignal | null;
    };
    composer: { getChatInput: () => HTMLTextAreaElement | null };
    conversation: { getCurrentConversation: () => Conversation | null };
    services: {
        getAttachmentManager: () => { getDraftRevision: () => number };
        getSoaiLinkResolutionManager: () => ComposerSoaiLinkResolutionManager;
        getChatApi: () => {
            webui: {
                chat: {
                    soaiLinks: {
                        resolve: (conversationId: string, payload: { rawText: string }, options: { signal: AbortSignal }) => Promise<SoaiLinkResolveResponse>;
                    };
                };
            };
        };
    };
}

const mergeTextAttachmentFragments = (payload: ComposerPayload): ComposerPayload => {
    const attachmentContent: ChatContentSegment[] = [];
    const textParts: string[] = payload.messageText ? [payload.messageText] : [];
    for (const fragment of payload.attachmentContent) {
        if (isPlainObject(fragment) && fragment['type'] === 'text' && isString(fragment['text'])) {
            textParts.push(fragment['text']);
            continue;
        }
        attachmentContent.push(fragment);
    }
    return {
        messageText: textParts.join('\n\n'),
        sourceText: payload.sourceText,
        attachmentContent,
        attachments: payload.attachments,
        draftRevision: payload.draftRevision
    };
};

const stripResolvedMessageText = (messageText: string): string => stripSoaiPathTokensForDisplay(messageText).trim();

const readComposerInputText = (host: SoaiLinkPayloadResolveHost): string => {
    const input = host.composer.getChatInput();
    return input instanceof HTMLTextAreaElement ? input.value.trim() : '';
};

const cloneComposerPayload = (payload: ComposerPayload): ComposerPayload => ({
    messageText: payload.messageText,
    sourceText: payload.sourceText,
    attachmentContent: [...payload.attachmentContent],
    attachments: [...payload.attachments],
    draftRevision: payload.draftRevision
});

const isResolveSnapshotCurrent = (host: SoaiLinkPayloadResolveHost, conversationId: string, snapshot: SoaiLinkResolveSnapshot, payload: ComposerPayload, signal: AbortSignal): boolean => {
    if (signal.aborted || host.conversation.getCurrentConversation()?.id !== conversationId || !matchesSoaiLinkWorkspaceSnapshot(host.conversation.getCurrentConversation(), snapshot.workspaceSnapshot) || (payload.draftRevision !== null && host.services.getAttachmentManager().getDraftRevision() !== payload.draftRevision)) {
        return false;
    }
    const resolutionManager = host.services.getSoaiLinkResolutionManager();
    if (snapshot.type === 'payload') {
        return resolutionManager.isPayloadResolveSeqCurrent(snapshot.requestSeq);
    }
    return resolutionManager.isComposerSubmitResolveSeqCurrent(snapshot.requestSeq) && readComposerInputText(host) === snapshot.messageText;
};

const resolveSoaiLinks = async (host: SoaiLinkPayloadResolveHost, conversationId: string, payload: ComposerPayload, resolveSnapshot: SoaiLinkResolveSnapshot, boundaryName: string, extraSignal: AbortSignal | null): Promise<ComposerPayload | null> => {
    const payloadSnapshot = cloneComposerPayload(payload);
    const mergedPayload = mergeTextAttachmentFragments(payloadSnapshot);
    const rawText = mergedPayload.messageText;
    if (!containsSoaiPathToken(rawText)) {
        return payloadSnapshot;
    }
    return await runWithAbortSignalScope([host.platform.getRuntimeAbortSignal(), extraSignal], async (signal) => {
        const response = await host.platform.runWithBoundary(boundaryName, () => host.services.getChatApi().webui.chat.soaiLinks.resolve(conversationId, { rawText: rawText }, { signal }));
        if (!isResolveSnapshotCurrent(host, conversationId, resolveSnapshot, payloadSnapshot, signal)) {
            return null;
        }
        const resolvedContentParts = requireMatchingResolveContentParts(response, rawText);
        if (!isResolveSnapshotCurrent(host, conversationId, resolveSnapshot, payloadSnapshot, signal)) {
            return null;
        }
        return {
            messageText: stripResolvedMessageText(mergedPayload.messageText),
            sourceText: mergedPayload.sourceText,
            attachmentContent: [...mergedPayload.attachmentContent, ...resolvedContentParts],
            attachments: mergedPayload.attachments,
            draftRevision: mergedPayload.draftRevision
        };
    });
};

const resolveComposerSoaiLinks = (host: SoaiLinkPayloadResolveHost, conversationId: string, payload: ComposerPayload): Promise<ComposerPayload | null> => {
    const resolutionManager = host.services.getSoaiLinkResolutionManager();
    return resolveSoaiLinks(
        host,
        conversationId,
        payload,
        {
            type: 'composer',
            requestSeq: resolutionManager.nextComposerSubmitResolveSeq(),
            messageText: payload.messageText,
            workspaceSnapshot: captureSoaiLinkWorkspaceSnapshot(host.conversation.getCurrentConversation())
        },
        'chat:resolveComposerSoaiLinks',
        null
    );
};

const resolvePayloadSoaiLinks = (host: SoaiLinkPayloadResolveHost, conversationId: string, payload: ComposerPayload, extraSignal: AbortSignal | null = null): Promise<ComposerPayload | null> => {
    const resolutionManager = host.services.getSoaiLinkResolutionManager();
    return resolveSoaiLinks(
        host,
        conversationId,
        payload,
        {
            type: 'payload',
            requestSeq: resolutionManager.nextPayloadResolveSeq(),
            workspaceSnapshot: captureSoaiLinkWorkspaceSnapshot(host.conversation.getCurrentConversation())
        },
        'chat:resolvePayloadSoaiLinks',
        extraSignal
    );
};

export { resolveComposerSoaiLinks, resolvePayloadSoaiLinks };
