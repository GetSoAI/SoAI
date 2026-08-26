/* SoAI - Chat feature message view contracts [frontend/assets/ts/features/chat/message/messageview/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AgentCanonicalPlan } from '@core/chat/agentTypes.ts';
import type { SyntaxHighlighterLanguagesTranslationKey } from '@core/i18n/translationkeys/syntaxhighlighter/languages.generated.ts';
import type { CodeBlockDescriptor, RichTextTableMode } from '@core/richtextrenderer/service.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { ChatActivityDurationDisplayMode } from '@features/chat/message/messageview/activityDurationDisplay.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { ImageSegment, InlineActionUpdateSegment, InlineLoadingActivitySegment, InlineProcessingActivitySegment, InlineToolActivitySegment, InlineThinkingActivitySegment, InlineWaitForUserActivitySegment, MessageSegment, SoaiFileSegment, SoaiFileUnavailableSegment, SoaiKnowledgeSegment, SoaiKnowledgeUnavailableSegment, SoaiPathSegment, ToolCallSegment } from '@features/chat/message/messageSegments.ts';

type ChatMessageTranslationKey =
    | 'chat.comparison.navigation.next'
    | 'chat.comparison.navigation.previous'
    | 'chat.loading.label'
    | 'chat.loading.modelPreview'
    | 'chat.message.actions.copyCode'
    | 'chat.attachments.badge.attachment'
    | 'chat.attachments.badge.knowledge'
    | 'chat.attachments.badge.soaiLink'
    | 'chat.attachments.openAttachment'
    | 'chat.attachments.openKnowledge'
    | 'chat.attachments.openSoaiLink'
    | 'chat.message.actions.undoDelete'
    | 'chat.message.deleted'
    | 'chat.message.generatedImage'
    | 'chat.message.renderFailed'
    | 'chat.message.toolCall'
    | 'chat.notifications.requestCancelled'
    | 'chat.processing.label'
    | 'chat.thinking.label'
    | 'chat.activityWidgets.requestedAt'
    | 'chat.news.articleCount'
    | 'chat.news.articles'
    | 'chat.news.label'
    | 'chat.news.noImage'
    | 'chat.news.readFullArticle'
    | 'chat.agent.plan.viewPlan'
    | 'chat.planWidget.execute'
    | 'chat.planWidget.label'
    | 'chat.planWidget.metrics'
    | 'chat.planWidget.revision'
    | 'chat.weather.clouds'
    | 'chat.weather.compass.e'
    | 'chat.weather.compass.n'
    | 'chat.weather.compass.ne'
    | 'chat.weather.compass.nw'
    | 'chat.weather.compass.s'
    | 'chat.weather.compass.se'
    | 'chat.weather.compass.sw'
    | 'chat.weather.compass.w'
    | 'chat.weather.feelsLike'
    | 'chat.weather.forecast'
    | 'chat.weather.hourly'
    | 'chat.weather.humidity'
    | 'chat.weather.label'
    | 'chat.weather.precipitation'
    | 'chat.weather.units.imperial'
    | 'chat.weather.units.metric'
    | 'chat.weather.wind'
    | 'chat.toolActivity.codeDiff'
    | 'chat.toolActivity.compactionMetadata'
    | 'chat.toolActivity.compactionPrompt'
    | 'chat.toolActivity.compactionSummary'
    | 'chat.toolActivity.removeCompactionBoundary'
    | 'chat.toolActivity.stopShell'
    | 'chat.toolActivity.stopShellHeader'
    | 'chat.toolActivity.diffTruncated'
    | 'chat.toolActivity.error'
    | 'chat.toolActivity.fileView'
    | 'chat.toolActivity.fileViewPartial'
    | 'chat.toolActivity.request'
    | 'chat.toolActivity.result'
    | 'chat.toolActivity.image'
    | 'chat.toolActivity.screenshot'
    | 'chat.toolActivity.video'
    | 'chat.toolActivity.videoFrames'
    | 'chat.toolActivity.transcript'
    | 'chat.toolActivity.status.completed'
    | 'chat.toolActivity.status.error'
    | 'chat.toolActivity.status.pending'
    | 'chat.toolActivity.status.running'
    | 'chat.toolActivity.subagentAdditionalContext'
    | 'chat.toolActivity.subagentPrompt'
    | 'chat.toolActivity.subagentStatus'
    | 'chat.toolActivity.subagentStream'
    | 'chat.toolActivity.truncatedChars'
    | 'chat.toolActivity.viewFullOutput'
    | 'chat.waitForUser.label'
    | 'common.close'
    | 'common.copy'
    | 'common.notAvailableShort'
    | 'common.placeholders.emptyCodeBlock'
    | 'common.placeholders.plainTextCodeBlockLanguage'
    | 'common.time.units.day.short'
    | 'common.view'
    | 'contentPreview.actions.openSource'
    | 'richText.footnotes.backToReference';

type ChatMessageWorkerTranslationKey = ChatMessageTranslationKey | SyntaxHighlighterLanguagesTranslationKey;

interface ChatMessageRenderHost {
    nowMs: () => number;
    getCanonicalPlan: () => AgentCanonicalPlan | null;
    escapeHtml: (unsafe: string) => string;
    escapeAttribute: (value: string) => string;
    sanitizeImage: (value: string) => string | null;
    getIconHtml: (name: IconName, options?: IconOptions) => string;
    getToolIconHtml: (toolName: string) => string | null;
    isRichTextEnabled: () => boolean;
    isInlineMultimediaPreviewsEnabled: () => boolean;
    isShowActivitiesEnabled: () => boolean;
    getActivityDurationDisplayMode: () => ChatActivityDurationDisplayMode;
    isCurrentConversationExecuting: () => boolean;
    renderRichText: (content: string, wrapCodeBlock: (descriptor: CodeBlockDescriptor) => string, options?: { tableMode?: RichTextTableMode; tableSortAction?: string }) => string;
}

interface SegmentTextResolution {
    value: string;
}

type MessageRenderOptions = {
    hideDefaultImageLabel?: boolean;
    compactAttachmentCards?: boolean;
    conversationId?: string | null;
    loadingActivityToggleAction?: string;
    loadingActivityToggleEnabled?: boolean;
    sortableTextTables?: boolean;
};

type RenderedMessageTextContent = {
    html: string;
    resolvedSegments: MessageSegment[] | null;
};

export type { ChatMessageRenderHost, ChatMessageTranslationKey, ChatMessageWorkerTranslationKey, ImageSegment, InlineActionUpdateSegment, InlineLoadingActivitySegment, InlineProcessingActivitySegment, InlineThinkingActivitySegment, InlineToolActivitySegment, InlineWaitForUserActivitySegment, MessageRenderOptions, MessageSegment, RenderedMessageTextContent, SegmentTextResolution, SoaiFileSegment, SoaiFileUnavailableSegment, SoaiKnowledgeSegment, SoaiKnowledgeUnavailableSegment, SoaiPathSegment, ToolCallSegment };
