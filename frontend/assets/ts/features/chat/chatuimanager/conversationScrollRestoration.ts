/* SoAI - Anchored conversation scroll restoration lifecycle [frontend/assets/ts/features/chat/chatuimanager/conversationScrollRestoration.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { prefersReducedMotion } from '@core/animations/prefersReducedMotion.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { acquireMainTimelineCoordinator } from '@features/chat/mainTimelineCoordinator.ts';
import { CHAT_SELECTORS } from '@features/chat/chatConstants.ts';
import { isMainTimelineUserScrollIntent, markUserScrollIntent, syncAutoScrollLockAttribute } from '@features/chat/chatuimanager/autoScrollLockRuntime.ts';
import { captureFirstVisibleMessageAnchor, resolveMessageScrollAnchorScrollTop, type MessageWindowScrollAnchor } from '@features/chat/chatuimanager/messageWindowScrollAnchor.ts';
import type { ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';
import { isMainTimelineAtBottom, writeMainTimelineScrollTop } from '@features/chat/mainTimelineScroll.ts';
import { resolvePersistedMessageCursor } from '@features/chat/message/persistedMessageIdentity.ts';
import type { MessageCursor } from '@features/chat/storage/storageModels.ts';
import type { ConversationContract } from '@features/chat/ChatTypes.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

const CONVERSATION_SCROLL_SNAPSHOT_PERSIST_DELAY_MS = 250;
const SMOOTH_SCROLL_DURATION_MS = 500;
const SMOOTH_SCROLL_MAX_FRAME_STEP_MS = 50;
const SMOOTH_SCROLL_DEADLINE_MS = 4000;
const RESTORE_INTENT_EVENTS = ['wheel', 'touchstart', 'pointerdown'];

const resolveRestorationScrollTop = (messagesArea: HTMLElement, renderAnchor: MessageWindowScrollAnchor | 'bottom'): number | null => {
    if (renderAnchor === 'bottom') return Math.max(0, messagesArea.scrollHeight - messagesArea.clientHeight);
    const target = resolveMessageScrollAnchorScrollTop(messagesArea, renderAnchor);
    return target === null ? null : clampNumber(target, 0, Math.max(0, messagesArea.scrollHeight - messagesArea.clientHeight));
};

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

const clearConversationScrollSnapshotPersistTimer = (context: ChatUIManagerContext): boolean => {
    const timer = context.state.conversationScrollSnapshotPersistTimer;
    if (timer === null) return false;
    context.dependencies.runtime.clearTimer(timer);
    context.state.conversationScrollSnapshotPersistTimer = null;
    return true;
};

const scheduleConversationScrollSnapshotPersist = (context: ChatUIManagerContext): void => {
    clearConversationScrollSnapshotPersistTimer(context);
    context.state.conversationScrollSnapshotPersistTimer = context.dependencies.runtime.setTimer(() => {
        context.state.conversationScrollSnapshotPersistTimer = null;
        context.dependencies.navigation.persistConversationScrollSnapshots();
    }, CONVERSATION_SCROLL_SNAPSHOT_PERSIST_DELAY_MS);
};

const flushConversationScrollSnapshots = (context: ChatUIManagerContext): void => {
    if (clearConversationScrollSnapshotPersistTimer(context)) context.dependencies.navigation.persistConversationScrollSnapshots();
};

const setupConversationScrollSnapshotPersistence = (context: ChatUIManagerContext): (() => void) => {
    const view = context.dependencies.dom.getDocument().defaultView;
    return view === null ? () => {} : context.dependencies.runtime.on(view, 'pagehide', () => flushConversationScrollSnapshots(context));
};

const isConversationScrollRestoreActive = (context: ChatUIManagerContext): boolean => context.state.activeConversationScrollRestore !== null;

const captureCurrentConversationScrollSnapshot = (context: ChatUIManagerContext): void => {
    if (isConversationScrollRestoreActive(context)) return;
    const conversationId = normalizeConversationId(context.dependencies.session.getCurrentConversationId());
    if (!conversationId) return;
    if (context.state.pendingConversationScrollRestoreConversationId === conversationId || context.state.failedConversationScrollRestoreConversationId === conversationId) return;
    const messagesArea = context.dependencies.optionalUI(CHAT_SELECTORS.MESSAGES_AREA);
    if (!(messagesArea instanceof HTMLElement)) return;
    const conversation = context.dependencies.session.getCurrentConversation();
    const renderAnchor = captureFirstVisibleMessageAnchor(messagesArea);
    const cursor = renderAnchor === null ? null : resolveScrollAnchorCursor(context, conversation, renderAnchor);
    if (renderAnchor === null || cursor === null) return;
    const followLatest = isMainTimelineAtBottom(messagesArea) && conversation?.history?.hasNewer !== true;
    context.dependencies.navigation.rememberConversationScrollSnapshot(conversationId, { cursor, renderAnchor, followLatest });
    scheduleConversationScrollSnapshotPersist(context);
};

const resolveConversationScrollRestoreCursor = (context: ChatUIManagerContext, conversationId: string): MessageCursor | null => {
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId) return null;
    const snapshot = context.dependencies.navigation.getConversationScrollSnapshot(normalizedConversationId);
    return snapshot === null || snapshot.followLatest ? null : { ...snapshot.cursor };
};

const prepareConversationScrollRestore = (context: ChatUIManagerContext, conversationId: string | null): boolean => {
    const normalizedConversationId = normalizeConversationId(conversationId);
    context.state.conversationScrollRestoreGeneration += 1;
    cancelActiveConversationScrollRestore(context, false);
    context.state.failedConversationScrollRestoreConversationId = null;
    context.state.pendingConversationScrollRestoreConversationId = normalizedConversationId || null;
    if (!normalizedConversationId) return false;
    const snapshot = context.dependencies.navigation.getConversationScrollSnapshot(normalizedConversationId);
    return snapshot !== null && !snapshot.followLatest;
};

const consumeConversationScrollRestore = (context: ChatUIManagerContext): { conversationId: string; renderAnchor: MessageWindowScrollAnchor | 'bottom' } | null => {
    const pendingConversationId = normalizeConversationId(context.state.pendingConversationScrollRestoreConversationId);
    const currentConversationId = normalizeConversationId(context.dependencies.session.getCurrentConversationId());
    if (!pendingConversationId || pendingConversationId !== currentConversationId) return null;
    const snapshot = context.dependencies.navigation.getConversationScrollSnapshot(pendingConversationId);
    context.state.pendingConversationScrollRestoreConversationId = null;
    return { conversationId: pendingConversationId, renderAnchor: snapshot === null || snapshot.followLatest ? 'bottom' : { ...snapshot.renderAnchor } };
};

const disposeActiveRestoreLifecycle = (context: ChatUIManagerContext, active: NonNullable<ChatUIManagerContext['state']['activeConversationScrollRestore']>): void => {
    if (active.deadlineTimer !== null) context.dependencies.runtime.clearTimer(active.deadlineTimer);
    for (const dispose of active.disposers) dispose();
    active.deadlineTimer = null;
    active.disposers = [];
};

const releaseActiveRestore = (context: ChatUIManagerContext, cancelled: boolean, notifyCompletion: boolean): void => {
    const active = context.state.activeConversationScrollRestore;
    if (active === null) return;
    disposeActiveRestoreLifecycle(context, active);
    if (context.state.activeConversationScrollRestore === active) {
        context.state.activeConversationScrollRestore = null;
        if (cancelled && notifyCompletion && active.renderAnchor !== 'bottom' && !context.state.autoScrollUserIntentActive && normalizeConversationId(context.dependencies.session.getCurrentConversationId()) === active.conversationId) {
            context.state.failedConversationScrollRestoreConversationId = active.conversationId;
        }
        syncAutoScrollLockAttribute(context, active.messagesArea);
    }
    if (notifyCompletion) active.completion(cancelled);
};

function cancelActiveConversationScrollRestore(context: ChatUIManagerContext, notifyCompletion: boolean): void {
    releaseActiveRestore(context, true, notifyCompletion);
}

const beginConversationScrollRestore = (context: ChatUIManagerContext, messagesArea: HTMLElement, onCompletion: RestoreCompletion, destination: 'saved-position' | 'bottom' = 'saved-position'): boolean => {
    const conversationId = normalizeConversationId(context.dependencies.session.getCurrentConversationId());
    if (destination === 'bottom' && !conversationId) return false;
    if (destination === 'bottom') {
        context.state.conversationScrollRestoreGeneration += 1;
        cancelActiveConversationScrollRestore(context, true);
        context.state.pendingConversationScrollRestoreConversationId = null;
        context.state.failedConversationScrollRestoreConversationId = null;
    }
    const restore: { conversationId: string; renderAnchor: MessageWindowScrollAnchor | 'bottom' } | null = destination === 'bottom' ? (conversationId ? { conversationId, renderAnchor: 'bottom' } : null) : consumeConversationScrollRestore(context);
    if (restore === null) return false;
    const initialTargetScrollTop = resolveRestorationScrollTop(messagesArea, restore.renderAnchor);
    if (initialTargetScrollTop === null) {
        if (restore.renderAnchor !== 'bottom') context.state.failedConversationScrollRestoreConversationId = restore.conversationId;
        return false;
    }
    const messagesRoot = context.dependencies.optionalUI(CHAT_SELECTORS.MESSAGES, messagesArea);
    if (!(messagesRoot instanceof HTMLElement)) throw new Error('Chat messages timeline is required for scroll restoration');
    const generation = context.state.conversationScrollRestoreGeneration;
    let deadline = performance.now() + SMOOTH_SCROLL_DEADLINE_MS;
    const complete = (cancelled: boolean): void => {
        const active = context.state.activeConversationScrollRestore;
        if (active === null || active.generation !== generation || active.messagesArea !== messagesArea) return;
        const currentConversationId = normalizeConversationId(context.dependencies.session.getCurrentConversationId());
        const wasCancelled = cancelled || !messagesArea.isConnected || currentConversationId !== active.conversationId;
        const settledTarget = wasCancelled ? null : resolveRestorationScrollTop(messagesArea, active.renderAnchor);
        const missedTarget = settledTarget === null || Math.abs(settledTarget - messagesArea.scrollTop) > 1;
        releaseActiveRestore(context, wasCancelled || missedTarget, true);
    };
    const active: NonNullable<ChatUIManagerContext['state']['activeConversationScrollRestore']> = { conversationId: restore.conversationId, generation, messagesArea, renderAnchor: restore.renderAnchor, disposers: [], deadlineTimer: null, completion: onCompletion };
    context.state.activeConversationScrollRestore = active;
    context.state.autoScrollEnabled = false;
    context.state.autoScrollUserIntentActive = false;
    syncAutoScrollLockAttribute(context, messagesArea);
    const coordinator = acquireMainTimelineCoordinator(messagesArea, messagesRoot);
    active.disposers.push(() => coordinator.cancelFrame('conversation-scroll-restore'), coordinator.release);
    let targetScrollTop = initialTargetScrollTop;
    let originScrollTop = messagesArea.scrollTop;
    let segmentStartedAt: number | null = null;
    let previousFrameAt: number | null = null;
    let pausedAt: number | null = null;
    const measureFrame = (): (() => void) | null => {
        if (context.state.activeConversationScrollRestore !== active || pauseWhileHidden()) return null;
        const currentConversationId = normalizeConversationId(context.dependencies.session.getCurrentConversationId());
        const currentTarget = resolveRestorationScrollTop(messagesArea, active.renderAnchor);
        if (!messagesArea.isConnected || currentConversationId !== active.conversationId || currentTarget === null) {
            cancelActiveConversationScrollRestore(context, true);
            return null;
        }
        const now = performance.now();
        if (now >= deadline) {
            cancelActiveConversationScrollRestore(context, true);
            return null;
        }
        if (segmentStartedAt === null) segmentStartedAt = now;
        else if (previousFrameAt !== null) segmentStartedAt += Math.max(0, now - previousFrameAt - SMOOTH_SCROLL_MAX_FRAME_STEP_MS);
        previousFrameAt = now;
        if (Math.abs(currentTarget - targetScrollTop) > 1) {
            targetScrollTop = currentTarget;
            if (active.renderAnchor !== 'bottom') {
                originScrollTop = messagesArea.scrollTop;
                segmentStartedAt = now;
            }
        }
        const progress = clampNumber((now - segmentStartedAt) / SMOOTH_SCROLL_DURATION_MS, 0, 1);
        const nextTop = originScrollTop + (targetScrollTop - originScrollTop) * (1 - (1 - progress) ** 3);
        return () => {
            if (context.state.activeConversationScrollRestore !== active || pausedAt !== null) return;
            writeMainTimelineScrollTop(messagesArea, nextTop);
            if (progress === 1) complete(false);
            else coordinator.scheduleFrame('conversation-scroll-restore', measureFrame);
        };
    };
    const pauseWhileHidden = (): boolean => {
        if (messagesArea.ownerDocument.visibilityState !== 'hidden') return false;
        if (pausedAt === null) {
            pausedAt = Math.min(performance.now(), previousFrameAt ?? deadline - SMOOTH_SCROLL_DEADLINE_MS);
            if (active.deadlineTimer !== null) context.dependencies.runtime.clearTimer(active.deadlineTimer);
            active.deadlineTimer = null;
            coordinator.cancelFrame('conversation-scroll-restore');
        }
        return true;
    };
    const armDeadline = (): void => {
        const timer: number | null = context.dependencies.runtime.setTimer(
            () => {
                if (context.state.activeConversationScrollRestore !== active || active.deadlineTimer !== timer) return;
                active.deadlineTimer = null;
                if (!pauseWhileHidden()) cancelActiveConversationScrollRestore(context, true);
            },
            Math.max(0, deadline - performance.now())
        );
        active.deadlineTimer = timer;
    };
    const syncVisibility = (): void => {
        if (context.state.activeConversationScrollRestore !== active || pauseWhileHidden() || pausedAt === null) return;
        const pausedDuration = Math.max(0, performance.now() - pausedAt);
        deadline += pausedDuration;
        if (segmentStartedAt !== null) segmentStartedAt += pausedDuration;
        if (previousFrameAt !== null) previousFrameAt += pausedDuration;
        pausedAt = null;
        armDeadline();
        coordinator.scheduleFrame('conversation-scroll-restore', measureFrame);
    };
    const cancelFromUserIntent = (event: Event): void => {
        if (isMainTimelineUserScrollIntent(event, messagesArea)) {
            markUserScrollIntent(context);
            cancelActiveConversationScrollRestore(context, true);
        }
    };
    for (const eventName of RESTORE_INTENT_EVENTS) active.disposers.push(context.dependencies.runtime.on(messagesArea, eventName, cancelFromUserIntent, { passive: true }));
    active.disposers.push(context.dependencies.runtime.on(context.dependencies.dom.getDocument(), 'keydown', cancelFromUserIntent, { passive: true }));
    if (prefersReducedMotion(messagesArea) || targetScrollTop === messagesArea.scrollTop) {
        writeMainTimelineScrollTop(messagesArea, targetScrollTop);
        complete(false);
        return true;
    }
    active.disposers.push(context.dependencies.runtime.on(messagesArea.ownerDocument, 'visibilitychange', syncVisibility, { passive: true }));
    if (pauseWhileHidden()) return true;
    armDeadline();
    coordinator.scheduleFrame('conversation-scroll-restore', measureFrame);
    return true;
};

const forgetConversationScrollSnapshot = (context: ChatUIManagerContext, conversationId: string): void => {
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId) return;
    context.dependencies.navigation.forgetConversationScrollSnapshot(normalizedConversationId);
    if (context.state.failedConversationScrollRestoreConversationId === normalizedConversationId) context.state.failedConversationScrollRestoreConversationId = null;
    scheduleConversationScrollSnapshotPersist(context);
    if (context.state.activeConversationScrollRestore?.conversationId === normalizedConversationId) cancelActiveConversationScrollRestore(context, false);
};

const disposeConversationScrollRestoration = (context: ChatUIManagerContext): void => {
    context.state.conversationScrollRestoreGeneration += 1;
    cancelActiveConversationScrollRestore(context, false);
    context.state.failedConversationScrollRestoreConversationId = null;
    context.state.pendingConversationScrollRestoreConversationId = null;
    flushConversationScrollSnapshots(context);
};

export { beginConversationScrollRestore, cancelActiveConversationScrollRestore, captureCurrentConversationScrollSnapshot, disposeConversationScrollRestoration, forgetConversationScrollSnapshot, isConversationScrollRestoreActive, prepareConversationScrollRestore, resolveConversationScrollRestoreCursor, setupConversationScrollSnapshotPersistence };
