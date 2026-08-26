/* SoAI - Shared chat protocols [frontend/assets/ts/core/chat/protocols.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonRecord, JsonValue } from '@core/types/jsonValues.ts';
import type { KnowledgeAttachmentSummary } from '@core/api/contracts/webuiAttachmentContracts.ts';

const CHAT_STREAM_SERVICE_ID = 'features.chat.chatStreamService';
const CHAT_PAGE_PRESENCE_SERVICE_ID = 'features.chat.chatPagePresence';
const CHAT_CONVERSATION_ATTENTION_SERVICE_ID = 'features.chat.conversationAttention';
const CHAT_TOOL_ICON_SERVICE_ID = 'features.chat.toolIconService';
const CHAT_RAG_INGESTION_SERVICE_ID = 'features.chat.ragIngestion';
const AUTO_EMBEDDING_MODEL_SELECTOR = '__soai_auto_embedding__';
const MAX_CHAT_COMPOSER_TEXT_LENGTH = 32768;

type ChatStreamStatus = 'streaming' | 'complete' | 'error' | 'cancelled';
type ChatConversationTerminalIndicator = 'complete' | 'error';
type ConversationExecutionRunResult = { status: 'completed' } | { status: 'busy' };

type ChatStreamServiceLifecycleContract = {
    initialize: () => void;
    dispose: () => void;
};

type ChatToolIconServiceContract = {
    ensureLoaded(): Promise<void>;
    getToolIcon(toolName: string): string | null;
};

type ChatRagIngestionStartArguments = {
    conversationId: string;
    files: File[];
    attachmentSource: 'composer_document_upload' | 'composer_folder_upload' | 'knowledge_tab_document_upload' | 'knowledge_tab_folder_upload';
};

type ChatRagIngestionStatus = {
    conversationId: string;
    clientBatchId: string | null;
    state: 'running' | 'paused' | 'submitted' | 'cancelled';
    total: number;
    queued: number;
    inFlight: number;
    succeeded: number;
    failed: number;
    skipped: number;
    lastError: string | null;
    knowledgeAttachment: KnowledgeAttachmentSummary | null;
};

type ChatRagIngestionServiceContract = {
    getStatusForConversation(conversationId: string): ChatRagIngestionStatus | null;
    start(inputArguments: ChatRagIngestionStartArguments): Promise<void>;
    cancel(conversationId: string): Promise<void>;
    subscribe(handler: () => void): () => void;
};

type ChatUiStorage = {
    ready: Promise<void>;
    session?: { userId?: string; username?: string; [key: string]: JsonValue };
    getChatPreferences(): JsonValue;
    setChatPreferences(preferences: JsonRecord): void;
    getChatWidescreenMode(): boolean;
    setChatWidescreenMode(value: boolean): void;
    getChatSidebarOpen(): boolean;
    setChatSidebarOpen(value: boolean): void;
    getChatShowFavoritesAtTop(): boolean;
    setChatShowFavoritesAtTop(value: boolean): void;
    getChatPlanBarVisible(): boolean;
    setChatPlanBarVisible(value: boolean): void;
    getCodeRecognitionEnabled(): boolean;
    getChatTextZoom(defaultZoom: number): number;
    setChatTextZoom(value: number): void;
    getAssistantAvatar(): string | null;
    setAssistantAvatar(value: string | null): void;
    getUserAvatar(): string | null;
    setUserAvatar(value: string | null): void;
};

export { AUTO_EMBEDDING_MODEL_SELECTOR, CHAT_CONVERSATION_ATTENTION_SERVICE_ID, CHAT_PAGE_PRESENCE_SERVICE_ID, CHAT_RAG_INGESTION_SERVICE_ID, CHAT_STREAM_SERVICE_ID, CHAT_TOOL_ICON_SERVICE_ID, MAX_CHAT_COMPOSER_TEXT_LENGTH };
export type { ChatConversationTerminalIndicator, ChatRagIngestionServiceContract, ChatRagIngestionStartArguments, ChatRagIngestionStatus, ChatStreamServiceLifecycleContract, ChatStreamStatus, ChatToolIconServiceContract, ChatUiStorage, ConversationExecutionRunResult };
