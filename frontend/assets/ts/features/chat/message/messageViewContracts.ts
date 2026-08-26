/* SoAI - Chat message view dependency contracts [frontend/assets/ts/features/chat/message/messageViewContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AgentCanonicalPlan } from '@core/chat/agentTypes.ts';
import type { SanitizerApi } from '@core/pagecontext/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { MessageSegment, ChatMessage } from '@features/chat/message/messageSegments.ts';
import type { ConversationMessage } from '@features/chat/ChatTypes.ts';
import type { ConversationRunningActivitySnapshot } from '@features/chat/storage/storageModels.ts';
import type { ChatActivityDurationDisplayMode } from '@features/chat/message/messageview/activityDurationDisplay.ts';
import type { RunningActivitySummary } from '@features/chat/toolactivity/runningActivitySummary.ts';

interface ChatMessagePresentationPreferencesPort {
    isThinkingFeatureEnabled: () => boolean;
    isRichTextEnabled: () => boolean;
    isCodeRecognitionEnabled: () => boolean;
    isInlineMultimediaPreviewsEnabled: () => boolean;
    isShowActivitiesEnabled: () => boolean;
    getActivityDurationDisplayMode: () => ChatActivityDurationDisplayMode;
}

interface ChatMessageAvatarPort {
    getAssistantAvatarUrl: () => string | null;
    getUserAvatarUrl: () => string | null;
}

interface ChatMessageViewDependencies {
    sanitizer: SanitizerApi;
    getCanonicalPlan: () => AgentCanonicalPlan | null;
    isConversationExecuting: (conversationId: string) => boolean;
    presentationPreferences: ChatMessagePresentationPreferencesPort;
    getIcon: (name: IconName, options?: IconOptions) => TrustedHtml;
    getToolIconHtml: (toolName: string) => string | null;
    getCurrentConversationId: () => string | null;
    getCurrentRunningActivitySnapshot: () => ConversationRunningActivitySnapshot | null;
    getMessageSenderLabel: (source: ConversationMessage, defaultRole: string) => string;
    resolveMessageContentSegments: (message: ChatMessage) => MessageSegment[];
    resolveRunningActivitySummaryForMarkup: (message: ChatMessage, nowMs: number) => RunningActivitySummary;
    getPreRenderedAssistantBodyHtml: (message: ChatMessage) => string | null;
    getLoadingActivityCollapsedState: (message: ChatMessage) => boolean | null;
    toggleLoadingActivityCollapsedState: (message: ChatMessage, defaultCollapsed: boolean) => boolean;
    handleError: (error: Error, context: string, options?: { notify?: boolean; severity?: 'debug' | 'info' | 'warn' | 'error'; rethrow?: boolean }) => void;
    avatars: ChatMessageAvatarPort;
}

export type { ChatMessageViewDependencies };
