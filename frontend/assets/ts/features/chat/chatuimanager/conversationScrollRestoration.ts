/* SoAI - Anchored conversation scroll restoration lifecycle [frontend/assets/ts/features/chat/chatuimanager/conversationScrollRestoration.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { prefersReducedMotion } from '@core/animations/prefersReducedMotion.ts';
import { CHAT_SELECTORS } from '@features/chat/chatConstants.ts';
import { isMainTimelineUserScrollIntent, syncAutoScrollLockAttribute } from '@features/chat/chatuimanager/autoScrollLockRuntime.ts';
import { captureFirstVisibleMessageAnchor, resolveMessageScrollAnchorScrollTop, type MessageWindowScrollAnchor } from '@features/chat/chatuimanager/messageWindowScrollAnchor.ts';
import type { ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';
import { resolvePersistedMessageCursor } from '@features/chat/message/persistedMessageIdentity.ts';
import type { MessageCursor } from '@features/chat/storage/storageModels.ts';
import type { ConversationContract } from '@features/chat/ChatTypes.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

const CONVERSATION_SCROLL_SNAPSHOT_LIMIT = 100;
const SMOOTH_SCROLL_SETTLE_DELAY_MS = 500;
const SMOOTH_SCROLL_INACTIVITY_DELAY_MS = 120;
const RESTORE_INTENT_EVENTS = ['wheel', 'touchstart', 'pointerdown'];

type RestoreCompletion = (cancelled: boolean) => void;

const resolveScrollAnchorCursor = (context: ChatUIManagerContext, conversation: ConversationContract | null, renderAnchor: MessageWindowScrollAnchor): MessageCursor | null => {
    const reference = context.dependencies.messageManager.resolveMessageReference(conversation, renderAnchor.messageId);
    const directCursor = reference?.message ? resolvePersistedMessageCursor(reference.message) : null;
    if (directCursor !== null || renderAnchor.assistantTurnTimestamp === null || conversation === null) return directCursor;
    for (const message of conversation.messages) {
        if (message.role !== 'assistant' || message.assistantTurnAtMs !== renderAnchor.assistantTurnTimestamp) continue;
        const cursor = resolvePersistedMessageCursor(message);
        if (cursor !== null) return cursor;
    }
    return null;
};

const trimConversationScrollSnapshots = (context: ChatUIManagerContext): void => {
    const snapshots = context.state.conversationScrollSnapshotByConversationId;
    while (snapshots.size > CONVERSATION_SCROLL_SNAPSHOT_LIMIT) {
        const oldestEntry = snapshots.keys().next();
        if (oldestEntry.done) return;
        snapshots.delete(oldestEntry.value);
    }
};

const isConversationScrollRestoreActive = (context: ChatUIManagerContext): boolean => context.state.activeConversationScrollRestore !== null;

const captureCurrentConversationScrollSnapshot = (context: ChatUIManagerContext): void => {
    if (isConversationScrollRestoreActive(context)) return;
    const conversationId = normalizeConversationId(context.dependencies.session.getCurrentConversationId());
    if (!conversationId) return;
    if (context.state.pendingConversationScrollRestoreConversationId === conversationId) return;
    const messagesArea = context.dependencies.optionalUI(CHAT_SELECTORS.MESSAGES_AREA);
    if (!(messagesArea instanceof HTMLElement)) return;
    const renderAnchor = captureFirstVisibleMessageAnchor(messagesArea);
    const cursor = renderAnchor === null ? null : resolveScrollAnchorCursor(context, context.dependencies.session.getCurrentConversation(), renderAnchor);
    if (renderAnchor === null || cursor === null) return;
    const snapshots = context.state.conversationScrollSnapshotByConversationId;
    snapshots.delete(conversationId);
    snapshots.set(conversationId, { cursor: { ...cursor }, renderAnchor: { ...renderAnchor } });
    trimConversationScrollSnapshots(context);
};

const resolveConversationScrollRestoreCursor = (context: ChatUIManagerContext, conversationId: string): MessageCursor | null => {
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId) return null;
    const snapshot = context.state.conversationScrollSnapshotByConversationId.get(normalizedConversationId);
    return snapshot === undefined ? null : { ...snapshot.cursor };
};

const prepareConversationScrollRestore = (context: ChatUIManagerContext, conversationId: string | null): boolean => {
    const normalizedConversationId = normalizeConversationId(conversationId);
    context.state.conversationScrollRestoreGeneration += 1;
    cancelActiveConversationScrollRestore(context, false);
    if (!normalizedConversationId || !context.state.conversationScrollSnapshotByConversationId.has(normalizedConversationId)) {
        context.state.pendingConversationScrollRestoreConversationId = null;
        return false;
    }
    context.state.pendingConversationScrollRestoreConversationId = normalizedConversationId;
    return true;
};

const consumeConversationScrollRestore = (context: ChatUIManagerContext): { conversationId: string; renderAnchor: MessageWindowScrollAnchor } | null => {
    const pendingConversationId = normalizeConversationId(context.state.pendingConversationScrollRestoreConversationId);
    const currentConversationId = normalizeConversationId(context.dependencies.session.getCurrentConversationId());
    if (!pendingConversationId || pendingConversationId !== currentConversationId) return null;
    const snapshot = context.state.conversationScrollSnapshotByConversationId.get(pendingConversationId);
    if (snapshot === undefined) return null;
    context.state.pendingConversationScrollRestoreConversationId = null;
    return { conversationId: pendingConversationId, renderAnchor: { ...snapshot.renderAnchor } };
};

const disposeActiveRestoreLifecycle = (context: ChatUIManagerContext, active: NonNullable<ChatUIManagerContext['state']['activeConversationScrollRestore']>): void => {
    if (active.settleTimer !== null) context.dependencies.runtime.clearTimer(active.settleTimer);
    for (const dispose of active.disposers) dispose();
    active.settleTimer = null;
    active.disposers = [];
};

const releaseActiveRestore = (context: ChatUIManagerContext): void => {
    const active = context.state.activeConversationScrollRestore;
    if (active === null) return;
    disposeActiveRestoreLifecycle(context, active);
    context.state.activeConversationScrollRestore = null;
};

function cancelActiveConversationScrollRestore(context: ChatUIManagerContext, notifyCompletion: boolean): void {
    const active = context.state.activeConversationScrollRestore;
    if (active === null) return;
    const completion = active.completion;
    disposeActiveRestoreLifecycle(context, active);
    if (active.messagesArea.isConnected) active.messagesArea.scrollTo({ top: active.messagesArea.scrollTop, behavior: 'auto' });
    if (context.state.activeConversationScrollRestore === active) context.state.activeConversationScrollRestore = null;
    if (notifyCompletion) completion(true);
}

const beginConversationScrollRestore = (context: ChatUIManagerContext, messagesArea: HTMLElement, onCompletion: RestoreCompletion): boolean => {
    const restore = consumeConversationScrollRestore(context);
    if (restore === null) return false;
    const targetScrollTop = resolveMessageScrollAnchorScrollTop(messagesArea, restore.renderAnchor);
    if (targetScrollTop === null) return false;
    const generation = context.state.conversationScrollRestoreGeneration;
    const complete = (cancelled: boolean): void => {
        const active = context.state.activeConversationScrollRestore;
        if (active === null || active.generation !== generation || active.messagesArea !== messagesArea) return;
        const currentConversationId = normalizeConversationId(context.dependencies.session.getCurrentConversationId());
        const wasCancelled = cancelled || !messagesArea.isConnected || currentConversationId !== active.conversationId;
        if (!wasCancelled) {
            const settledTarget = resolveMessageScrollAnchorScrollTop(messagesArea, active.renderAnchor);
            if (settledTarget !== null && settledTarget !== messagesArea.scrollTop) messagesArea.scrollTo({ top: settledTarget, behavior: 'auto' });
        }
        releaseActiveRestore(context);
        onCompletion(wasCancelled);
    };
    const active: NonNullable<ChatUIManagerContext['state']['activeConversationScrollRestore']> = { conversationId: restore.conversationId, generation, messagesArea, renderAnchor: restore.renderAnchor, disposers: [], settleTimer: null, completion: onCompletion };
    context.state.activeConversationScrollRestore = active;
    context.state.autoScrollEnabled = false;
    syncAutoScrollLockAttribute(context, messagesArea);
    if (prefersReducedMotion(messagesArea) || targetScrollTop === messagesArea.scrollTop) {
        messagesArea.scrollTo({ top: targetScrollTop, behavior: 'auto' });
        complete(false);
        return true;
    }
    const cancelFromUserIntent = (event: Event): void => {
        if (isMainTimelineUserScrollIntent(event, messagesArea)) cancelActiveConversationScrollRestore(context, true);
    };
    for (const eventName of RESTORE_INTENT_EVENTS) active.disposers.push(context.dependencies.runtime.on(messagesArea, eventName, cancelFromUserIntent, { passive: true }));
    active.disposers.push(context.dependencies.runtime.on(context.dependencies.dom.getDocument(), 'keydown', cancelFromUserIntent, { passive: true }));
    active.disposers.push(context.dependencies.runtime.on(messagesArea, 'scrollend', () => complete(false)));
    active.disposers.push(
        context.dependencies.runtime.on(
            messagesArea,
            'scroll',
            () => {
                if (active.settleTimer !== null) context.dependencies.runtime.clearTimer(active.settleTimer);
                active.settleTimer = context.dependencies.runtime.setTimer(() => complete(false), SMOOTH_SCROLL_INACTIVITY_DELAY_MS);
            },
            { passive: true }
        )
    );
    active.settleTimer = context.dependencies.runtime.setTimer(() => complete(false), SMOOTH_SCROLL_SETTLE_DELAY_MS);
    messagesArea.scrollTo({ top: targetScrollTop, behavior: 'smooth' });
    return true;
};

const forgetConversationScrollSnapshot = (context: ChatUIManagerContext, conversationId: string): void => {
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId) return;
    context.state.conversationScrollSnapshotByConversationId.delete(normalizedConversationId);
    if (context.state.pendingConversationScrollRestoreConversationId === normalizedConversationId) context.state.pendingConversationScrollRestoreConversationId = null;
    if (context.state.activeConversationScrollRestore?.conversationId === normalizedConversationId) cancelActiveConversationScrollRestore(context, false);
};

const disposeConversationScrollRestoration = (context: ChatUIManagerContext): void => {
    context.state.conversationScrollRestoreGeneration += 1;
    cancelActiveConversationScrollRestore(context, false);
    context.state.conversationScrollSnapshotByConversationId.clear();
    context.state.pendingConversationScrollRestoreConversationId = null;
};

export { beginConversationScrollRestore, cancelActiveConversationScrollRestore, captureCurrentConversationScrollSnapshot, disposeConversationScrollRestoration, forgetConversationScrollSnapshot, isConversationScrollRestoreActive, prepareConversationScrollRestore, resolveConversationScrollRestoreCursor };
