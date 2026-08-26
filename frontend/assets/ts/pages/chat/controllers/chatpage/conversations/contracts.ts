/* SoAI - Chat conversation view contract [frontend/assets/ts/pages/chat/controllers/chatpage/conversations/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatConversationTerminalIndicator } from '@core/chat/protocols.ts';
import type { Conversation, ConversationExecutionStatus } from '@features/chat/public.ts';
import type { ChatConversationActionsContract } from '@pages/chat/controllers/chatconversationactionscontroller/contracts.ts';
type ConversationAttentionStatus = 'none' | 'agent_plan_unseen';
type ChatConversationRenderOutcome = 'messages-unchanged' | 'dom-reconciled' | 'not-rendered' | 'superseded';

interface ConversationSidebarStatus {
    executionStatus: ConversationExecutionStatus;
    terminalStatus: ChatConversationTerminalIndicator | null;
    attentionStatus: ConversationAttentionStatus;
    isExecuting: boolean;
    isChatStreaming: boolean;
}

interface SidebarListReadiness {
    isCurrent(): boolean;
}

interface ConversationSidebarStatusSyncOptions {
    scheduleConversationListRender: boolean;
}

interface ChatConversationViewContract {
    initializeActions(actions: ChatConversationActionsContract): void;
    initializeSearch(): void;
    refresh(): Promise<void>;
    refreshListAndHeader(): Promise<void>;
    renderList(): Promise<void>;
    revealInList(conversationId: string): Promise<boolean>;
    syncSidebarListVisibility(visible: boolean): Promise<SidebarListReadiness>;
    renderCurrent(): Promise<void>;
    onRendered(handler: (outcome: ChatConversationRenderOutcome) => void): () => void;
    prepareMessages(conversationId: string): Promise<void>;
    current(): Conversation | null;
    invalidate(scope?: 'current' | 'list' | 'both'): void;
    refreshWorkerRendering(): void;
    invalidateMessagePresentation(): void;
    requireActions(): ChatConversationActionsContract;
    replaceRoute(conversationId: string | null, options?: { signal?: AbortSignal | null }): Promise<void>;
    isStreaming(conversationId: string): boolean;
    resolveSidebarStatus(conversationId: string): ConversationSidebarStatus;
    isExecuting(conversationId: string): boolean;
    syncSidebarStatus(conversationId: string, options: ConversationSidebarStatusSyncOptions): boolean;
    terminalIndicator(conversationId: string): ChatConversationTerminalIndicator | null;
    acknowledgeTerminalAttentionIfViewed(conversationId: string | null, assistantAtMs?: number | null): void;
    refreshActivityClock(): void;
    activeComparisonRun(conversationId: string): { assistantTurnTimestamp: number; variantCount: number } | null;
    reportFailure(error: Error): void;
    openEnsuringLoaded(conversationId: string): void;
    refreshSidebar(): Promise<void>;
    dispose(): void;
    initializeEmptyStateNavigation(container: Element): void;
}

export type { ChatConversationRenderOutcome, ChatConversationViewContract, ConversationAttentionStatus, ConversationSidebarStatus, ConversationSidebarStatusSyncOptions, SidebarListReadiness };
export interface ChatConversationViewHost {
    conversationView: ChatConversationViewContract;
}
