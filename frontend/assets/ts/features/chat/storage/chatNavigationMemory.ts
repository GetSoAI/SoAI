/* SoAI - Chat navigation memory [frontend/assets/ts/features/chat/storage/chatNavigationMemory.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseConversationId } from '@core/chat/conversationIdentifier.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import { readStorageJson, writeStorageJson } from '@core/storage/ttlStorageCache.ts';
import { isArray, isFiniteNumber, isNonEmptyString, isNonNegativeInteger, isPlainObject, isString } from '@core/typeGuards.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { MessageWindowScrollAnchor } from '@features/chat/chatuimanager/messageWindowScrollAnchor.ts';
import type { MessageCursor } from '@features/chat/storage/storageModels.ts';

const CHAT_NAVIGATION_MEMORY_SCOPE = 'ChatNavigationMemory';
const CONVERSATION_SCROLL_SNAPSHOT_LIMIT = 100;

type ConversationScrollSnapshot = Readonly<{
    cursor: MessageCursor;
    renderAnchor: MessageWindowScrollAnchor;
    followLatest: boolean;
}>;

interface ChatNavigationMemory {
    readLastConversationId(): string | null;
    rememberLastConversationId(conversationId: string | null): void;
    getConversationScrollSnapshot(conversationId: string): ConversationScrollSnapshot | null;
    rememberConversationScrollSnapshot(conversationId: string, snapshot: ConversationScrollSnapshot): void;
    forgetConversationScrollSnapshot(conversationId: string): void;
    persistConversationScrollSnapshots(): void;
}

interface ChatNavigationMemoryOptions {
    userId: string | null | undefined;
    isDetached(): boolean;
}

type ChatNavigationMemoryState = {
    lastConversationId: string | null;
    readonly scrollSnapshots: Map<string, ConversationScrollSnapshot>;
    readonly unpersistedScrollSnapshots: Map<string, ConversationScrollSnapshot | null>;
};

const navigationMemoryStateByUserId = new Map<string, ChatNavigationMemoryState>();

const lastConversationStorageKey = (userId: string): string => `soai.webui.chat-last-conversation-v1:${encodeURIComponent(userId)}`;

const scrollSnapshotsStorageKey = (userId: string): string => `soai.webui.chat-scroll-snapshots-v1:${encodeURIComponent(userId)}`;

const readStoredValue = (key: string): JsonValue | null => {
    try {
        return readStorageJson('localStorage', key);
    } catch (error) {
        errorHandler.warn(CHAT_NAVIGATION_MEMORY_SCOPE, 'Ignoring unreadable chat navigation memory', ensureError(error));
        return null;
    }
};

const writeStoredValue = (key: string, value: JsonValue): void => {
    try {
        writeStorageJson('localStorage', key, value);
    } catch (error) {
        errorHandler.warn(CHAT_NAVIGATION_MEMORY_SCOPE, 'Failed to persist chat navigation memory', ensureError(error));
    }
};

const decodeMessageCursor = (value: JsonValue | undefined): MessageCursor | null => {
    if (!isPlainObject(value)) return null;
    const createdAtMs = value['createdAtMs'];
    const id = value['id'];
    return isNonNegativeInteger(createdAtMs) && isNonNegativeInteger(id) ? { createdAtMs, id } : null;
};

const decodeRenderAnchor = (value: JsonValue | undefined): MessageWindowScrollAnchor | null => {
    if (!isPlainObject(value)) return null;
    const messageId = value['messageId'];
    const assistantTurnTimestamp = value['assistantTurnTimestamp'];
    const offsetTopWithinMessage = value['offsetTopWithinMessage'];
    if (!isNonEmptyString(messageId) || !isFiniteNumber(offsetTopWithinMessage)) return null;
    if (assistantTurnTimestamp !== null && !isNonNegativeInteger(assistantTurnTimestamp)) return null;
    return { messageId, assistantTurnTimestamp, offsetTopWithinMessage };
};

const trimScrollSnapshots = (snapshots: Map<string, ConversationScrollSnapshot>): void => {
    for (const conversationId of snapshots.keys()) {
        if (snapshots.size <= CONVERSATION_SCROLL_SNAPSHOT_LIMIT) return;
        snapshots.delete(conversationId);
    }
};

const setMostRecentScrollSnapshot = (snapshots: Map<string, ConversationScrollSnapshot>, conversationId: string, snapshot: ConversationScrollSnapshot): void => {
    snapshots.delete(conversationId);
    snapshots.set(conversationId, snapshot);
    trimScrollSnapshots(snapshots);
};

const readStoredScrollSnapshots = (userId: string): Map<string, ConversationScrollSnapshot> => {
    const snapshots = new Map<string, ConversationScrollSnapshot>();
    const stored = readStoredValue(scrollSnapshotsStorageKey(userId));
    if (!isArray(stored)) return snapshots;
    for (const entry of stored) {
        if (!isPlainObject(entry)) continue;
        const conversationIdValue = entry['conversationId'];
        const conversationId = isString(conversationIdValue) ? parseConversationId(conversationIdValue) : null;
        const cursor = decodeMessageCursor(entry['cursor']);
        const renderAnchor = decodeRenderAnchor(entry['renderAnchor']);
        if (conversationId === null || cursor === null || renderAnchor === null) continue;
        setMostRecentScrollSnapshot(snapshots, conversationId, { cursor, renderAnchor, followLatest: entry['followLatest'] === true });
    }
    return snapshots;
};

const encodeScrollSnapshots = (snapshots: ReadonlyMap<string, ConversationScrollSnapshot>): JsonObject[] => {
    const entries: JsonObject[] = [];
    for (const [conversationId, snapshot] of snapshots) {
        entries.push({
            conversationId,
            cursor: { createdAtMs: snapshot.cursor.createdAtMs, id: snapshot.cursor.id },
            renderAnchor: { messageId: snapshot.renderAnchor.messageId, assistantTurnTimestamp: snapshot.renderAnchor.assistantTurnTimestamp, offsetTopWithinMessage: snapshot.renderAnchor.offsetTopWithinMessage },
            followLatest: snapshot.followLatest
        });
    }
    return entries;
};

const readStoredLastConversationId = (userId: string): string | null => {
    const stored = readStoredValue(lastConversationStorageKey(userId));
    return isString(stored) ? parseConversationId(stored) : null;
};

const createNavigationMemoryState = (userId: string | null): ChatNavigationMemoryState => ({
    lastConversationId: userId === null ? null : readStoredLastConversationId(userId),
    scrollSnapshots: userId === null ? new Map() : readStoredScrollSnapshots(userId),
    unpersistedScrollSnapshots: new Map()
});

const resolveNavigationMemoryState = (userId: string | null): ChatNavigationMemoryState => {
    if (userId === null) return createNavigationMemoryState(null);
    const existing = navigationMemoryStateByUserId.get(userId);
    if (existing !== undefined) return existing;
    const created = createNavigationMemoryState(userId);
    navigationMemoryStateByUserId.set(userId, created);
    return created;
};

const persistScrollSnapshots = (userId: string | null, state: ChatNavigationMemoryState): void => {
    if (state.unpersistedScrollSnapshots.size === 0) return;
    if (userId === null) {
        state.unpersistedScrollSnapshots.clear();
        return;
    }
    const stored = readStoredScrollSnapshots(userId);
    for (const [conversationId, snapshot] of state.unpersistedScrollSnapshots) {
        if (snapshot === null) {
            stored.delete(conversationId);
        } else {
            setMostRecentScrollSnapshot(stored, conversationId, snapshot);
        }
    }
    state.unpersistedScrollSnapshots.clear();
    writeStoredValue(scrollSnapshotsStorageKey(userId), encodeScrollSnapshots(stored));
};

const createChatNavigationMemory = (options: ChatNavigationMemoryOptions): ChatNavigationMemory => {
    const userId = toTrimmedStringOrNull(options.userId);
    const state = resolveNavigationMemoryState(userId);
    return {
        readLastConversationId: (): string | null => (options.isDetached() ? null : state.lastConversationId),
        rememberLastConversationId: (conversationId: string | null): void => {
            if (options.isDetached()) return;
            const nextConversationId = conversationId === null ? null : parseConversationId(conversationId);
            if (nextConversationId === state.lastConversationId) return;
            state.lastConversationId = nextConversationId;
            if (userId !== null) writeStoredValue(lastConversationStorageKey(userId), nextConversationId);
        },
        getConversationScrollSnapshot: (conversationId: string): ConversationScrollSnapshot | null => state.scrollSnapshots.get(conversationId) ?? null,
        rememberConversationScrollSnapshot: (conversationId: string, snapshot: ConversationScrollSnapshot): void => {
            const storedSnapshot: ConversationScrollSnapshot = { cursor: { ...snapshot.cursor }, renderAnchor: { ...snapshot.renderAnchor }, followLatest: snapshot.followLatest };
            setMostRecentScrollSnapshot(state.scrollSnapshots, conversationId, storedSnapshot);
            state.unpersistedScrollSnapshots.set(conversationId, storedSnapshot);
        },
        forgetConversationScrollSnapshot: (conversationId: string): void => {
            state.scrollSnapshots.delete(conversationId);
            state.unpersistedScrollSnapshots.set(conversationId, null);
        },
        persistConversationScrollSnapshots: (): void => persistScrollSnapshots(userId, state)
    };
};

export { createChatNavigationMemory };
export type { ChatNavigationMemory, ConversationScrollSnapshot };
