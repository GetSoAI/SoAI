/* SoAI - Chat feature storage models [frontend/assets/ts/features/chat/storage/storageModels.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatUiParameters } from '@core/types/chatParameters.ts';
import type { ConversationSettingsAuthority } from '@core/chat/conversationSettingsAuthority.ts';
import type { MessagingPlatform } from '@core/chat/conversationSource.ts';
import type { ChatMessage, ConversationContract, MessageRole } from '@features/chat/ChatTypes.ts';
import type { ConversationModelSettings } from '@core/chat/executionSettingsTypes.ts';

type ChatParameters = ChatUiParameters;

type ChatStorageMessageRecord = ChatMessage & {
    role: MessageRole;
    timestamp: number;
};

type MessageCursor = {
    createdAtMs: number;
    id: number;
};

type MessageWindowDirection = 'tail' | 'before' | 'after' | 'around';
type MessageWindowBackgroundDirection = 'before' | 'after';

type LoadConversationMessagesOptions = {
    signal?: AbortSignal;
    expectedMessageCount?: number;
    allowAuthoritativeCountDecrease?: boolean;
    force?: boolean;
    mergeStreamingAssistants?: boolean;
    direction?: MessageWindowDirection;
    cursor?: MessageCursor;
    anchor?: MessageCursor;
    limit?: number;
};

type ConversationMessageRange = {
    firstCursor: MessageCursor;
    lastCursor: MessageCursor;
    messages: ChatStorageMessageRecord[];
};

type RunningActivityTargetSnapshot = {
    assistantTurnAtMs: number;
    modelVariantIndex: number;
    messageCursor: MessageCursor;
    callId: string;
    ancestorCallIds: string[];
    startedAtMs: number;
};

type ConversationRunningActivitySnapshot = {
    convId: string;
    activityCount: number;
    backgroundActivityCount: number;
    backgroundSubagentCount: number;
    backgroundTarget: RunningActivityTargetSnapshot | null;
    subagentCount: number;
    target: RunningActivityTargetSnapshot | null;
    lastModifiedAtMs: number;
};

type ConversationHistoryState = {
    conversationId: string;
    version: number;
    totalCount: number;
    loadedUniqueCount: number;
    retainedRanges: ConversationMessageRange[];
    oldestCursor: MessageCursor | null;
    newestCursor: MessageCursor | null;
    hasOlder: boolean;
    hasNewer: boolean;
    blockingStatus: 'idle' | 'loading' | 'ready' | 'error';
    backgroundStatus: 'idle' | 'loading' | 'complete' | 'error';
    backgroundDirection: MessageWindowBackgroundDirection | null;
    runningActivity: ConversationRunningActivitySnapshot | null;
};

type Conversation = ConversationContract & {
    id: string;
    title: string;
    createdAt: number;
    updatedAt: number;
    modelSettings: ConversationModelSettings;
    isFavorite: boolean;
    color: string | null;
    settingsAuthority?: ConversationSettingsAuthority;
    isAutomation?: boolean;
    isMessaging?: boolean;
    messagingPlatform?: MessagingPlatform | null;
    messagingAccountLabel?: string | null;
    messagingAccountSnapshotId?: string | null;
    isArchived?: boolean;
    compactionCount?: number;
    compactionTokensSaved?: number;
    messageCount?: number;
    messagesHydrated?: boolean;
    history?: ConversationHistoryState;
};

type ArchivedConversationSummary = {
    id: string;
    title: string;
    updatedAt: number;
    color: string | null;
    isFavorite: boolean;
    isAutomation: boolean;
    isMessaging: boolean;
    messagingPlatform: MessagingPlatform | null;
    messagingAccountLabel: string | null;
    messagingAccountSnapshotId: string | null;
    isArchived: boolean;
    settingsAuthority: ConversationSettingsAuthority;
    messageCount: number;
    compactionCount: number;
    compactionTokensSaved: number;
};

type ArchivedConversationsCursor = {
    lastModifiedAtMs: number;
    id: string;
};

type ArchivedConversationsPage = {
    conversations: ArchivedConversationSummary[];
    totalCount: number;
    nextCursor: ArchivedConversationsCursor | null;
};

type BackendConversation = Conversation;

export type { ArchivedConversationSummary, ArchivedConversationsCursor, ArchivedConversationsPage, ChatParameters, ChatStorageMessageRecord, Conversation, BackendConversation, ConversationHistoryState, ConversationMessageRange, ConversationRunningActivitySnapshot, LoadConversationMessagesOptions, MessageCursor, MessageWindowBackgroundDirection, MessageWindowDirection, RunningActivityTargetSnapshot };
