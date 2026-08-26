/* SoAI - Conversation export cover summary metrics [frontend/assets/ts/features/chat/conversationexport/coverMetrics.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { isFiniteNumber, isNonEmptyString } from '@core/typeGuards.ts';
import type { ChatMessage, ConversationContract } from '@features/chat/ChatTypes.ts';
import { isMessagingAccountConversation } from '@features/chat/conversation/conversationSettingsEligibility.ts';
import { resolveConversationExportActivitySummary } from '@features/chat/conversationexport/activitySummary.ts';
import type { ConversationExportTurn } from '@features/chat/conversationexport/turnModel.ts';
import { buildMessageContentSegments } from '@features/chat/message/messageSegmentsFromContent.ts';
import type { MessageSegment } from '@features/chat/message/messageSegments.ts';
import { resolveConversationExportUserSenderLabel } from '@features/chat/message/senderLabel.ts';

type ConversationExportSummaryItem = { label: string; value: string };

type ConversationExportModelCategory = 'local' | 'cloud' | 'virtual' | 'unknown';
type ConversationExportModelDescriptor = { name: string; category: ConversationExportModelCategory };
type ConversationExportModelResolver = (modelId: string) => ConversationExportModelDescriptor | null;

const modelCategoryLabel = (category: ConversationExportModelCategory): string => {
    switch (category) {
        case 'local':
            return i18n.t('chat.export.pdf.modelType.local');
        case 'cloud':
            return i18n.t('chat.export.pdf.modelType.cloud');
        case 'virtual':
            return i18n.t('chat.export.pdf.modelType.virtual');
        case 'unknown':
            return '';
    }
};

const formatModelLabel = (descriptor: ConversationExportModelDescriptor): string => {
    const typeLabel = modelCategoryLabel(descriptor.category);
    return typeLabel ? `${descriptor.name} (${typeLabel})` : descriptor.name;
};

const DATE_FORMAT: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
};
const MINUTE_MS = 60_000;
const HOUR_MINUTES = 60;
const DAY_MINUTES = 1_440;
const ATTACHMENT_SEGMENT_TYPES: ReadonlySet<MessageSegment['type']> = new Set(['image', 'soai_file', 'soai_knowledge', 'soai_file_unavailable', 'soai_knowledge_unavailable']);

const messageSegments = (message: ChatMessage): MessageSegment[] => buildMessageContentSegments(message.content);

const segmentText = (segments: readonly MessageSegment[]): string => {
    const parts: string[] = [];
    for (const segment of segments) {
        if (segment.type === 'text') {
            parts.push(segment.text);
        }
    }
    return parts.join('\n');
};

const countWords = (text: string): number => {
    const trimmed = text.trim();
    return trimmed ? trimmed.split(/\s+/).length : 0;
};

const countAttachments = (segments: readonly MessageSegment[]): number => {
    let count = 0;
    for (const segment of segments) {
        if (ATTACHMENT_SEGMENT_TYPES.has(segment.type)) {
            count += 1;
        }
    }
    return count;
};

type MessageTokenCounts = {
    total: number;
    prompt: number;
    completion: number;
};

const messageTokens = (message: ChatMessage): MessageTokenCounts => {
    const declaredTotal = isFiniteNumber(message.totalTokens) ? message.totalTokens : 0;
    const prompt = isFiniteNumber(message.promptTokens) ? message.promptTokens : 0;
    const completion = isFiniteNumber(message.completionTokens) ? message.completionTokens : 0;
    return { total: declaredTotal > 0 ? declaredTotal : prompt + completion, prompt, completion };
};

type RenderedMetrics = {
    models: string[];
    attachments: number;
    toolCalls: number;
    tokens: number;
    promptTokens: number;
    completionTokens: number;
    words: number;
    characters: number;
};

const collectRenderedMetrics = (turns: readonly ConversationExportTurn[], defaultModel: string | null, resolveModel: ConversationExportModelResolver): RenderedMetrics => {
    const models = new Set<string>();
    const addModel = (modelId: string | null | undefined): void => {
        if (!isNonEmptyString(modelId)) {
            return;
        }
        const descriptor = resolveModel(modelId);
        models.add(descriptor !== null ? formatModelLabel(descriptor) : modelId);
    };
    addModel(defaultModel);
    let attachments = 0;
    let toolCalls = 0;
    let tokens = 0;
    let promptTokens = 0;
    let completionTokens = 0;
    let words = 0;
    let characters = 0;
    for (const turn of turns) {
        for (const message of turn.messages) {
            const segments = messageSegments(message);
            const text = segmentText(segments);
            const tokenCounts = messageTokens(message);
            addModel(message.modelId);
            attachments += countAttachments(segments);
            toolCalls += resolveConversationExportActivitySummary(message, segments).toolCalls;
            tokens += tokenCounts.total;
            promptTokens += tokenCounts.prompt;
            completionTokens += tokenCounts.completion;
            words += countWords(text);
            characters += text.trim().length;
        }
    }
    return { models: Array.from(models), attachments, toolCalls, tokens, promptTokens, completionTokens, words, characters };
};

const humanizeSpan = (durationMs: number): string => {
    if (!(durationMs > MINUTE_MS)) {
        return '';
    }
    const totalMinutes = Math.floor(durationMs / MINUTE_MS);
    const days = Math.floor(totalMinutes / DAY_MINUTES);
    const hours = Math.floor((totalMinutes % DAY_MINUTES) / HOUR_MINUTES);
    const minutes = totalMinutes % HOUR_MINUTES;
    const parts: string[] = [];
    if (days > 0) {
        parts.push(i18n.t('chat.export.pdf.summary.spanDays', { count: days }));
    }
    if (hours > 0) {
        parts.push(i18n.t('chat.export.pdf.summary.spanHours', { count: hours }));
    }
    if (minutes > 0 && days === 0) {
        parts.push(i18n.t('chat.export.pdf.summary.spanMinutes', { count: minutes }));
    }
    return parts.slice(0, 2).join(' ');
};

const formatTimestamp = (timestampMs: number): string => i18n.formatDate(new Date(timestampMs), DATE_FORMAT);

const countTurnsByKind = (turns: readonly ConversationExportTurn[]): { total: number; user: number; assistant: number } => {
    let user = 0;
    let assistant = 0;
    for (const turn of turns) {
        if (turn.kind === 'user') {
            user += 1;
        } else if (turn.kind === 'assistant') {
            assistant += 1;
        }
    }
    return { total: turns.length, user, assistant };
};

const resolveConversationExportRoleSummaryLabel = (conversation: ConversationContract): string => {
    if (isMessagingAccountConversation(conversation)) {
        return i18n.t('chat.export.pdf.summary.participants');
    }
    return resolveConversationExportUserSenderLabel({
        conversation,
        message: null,
        fallbackLabel: i18n.t('chat.export.pdf.outline.role.user')
    });
};

const notAvailableValue = (): string => i18n.t('common.notAvailableShort');

const resolveTimestampValue = (timestampMs: number | null | undefined): string => (isFiniteNumber(timestampMs) ? formatTimestamp(timestampMs) : notAvailableValue());

const resolveSpanValue = (conversation: ConversationContract): string => {
    if (!isFiniteNumber(conversation.createdAt) || !isFiniteNumber(conversation.updatedAt)) {
        return notAvailableValue();
    }
    const span = humanizeSpan(conversation.updatedAt - conversation.createdAt);
    return span ? span : i18n.t('chat.export.pdf.summary.spanUnderMinute');
};

const resolveModelsValue = (models: readonly string[]): string => {
    if (models.length === 0) {
        return notAvailableValue();
    }
    const names = models.join(', ');
    if (models.length === 1) {
        return names;
    }
    return i18n.t('chat.export.pdf.summary.modelsValue', { count: models.length, models: names });
};

const resolvePromptCompletionValue = (metrics: RenderedMetrics): string => {
    if (metrics.promptTokens + metrics.completionTokens <= 0) {
        return notAvailableValue();
    }
    return i18n.t('chat.export.pdf.summary.promptCompletionValue', { prompt: metrics.promptTokens, completion: metrics.completionTokens });
};

const buildCoverSummaryItems = (turns: readonly ConversationExportTurn[], conversation: ConversationContract, defaultModel: string | null, resolveModel: ConversationExportModelResolver, exportedAt: Date): ConversationExportSummaryItem[] => {
    const roles = countTurnsByKind(turns);
    const metrics = collectRenderedMetrics(turns, defaultModel, resolveModel);
    const compactions = isFiniteNumber(conversation.compactionCount) && conversation.compactionCount > 0 ? Math.floor(conversation.compactionCount) : 0;
    const userLabel = resolveConversationExportRoleSummaryLabel(conversation);
    const items: ConversationExportSummaryItem[] = [
        { label: i18n.t('chat.export.pdf.summary.messages'), value: i18n.t('chat.export.pdf.summary.messagesValue', { ...roles, userLabel }) },
        { label: i18n.t('chat.export.pdf.summary.attachments'), value: String(metrics.attachments) },
        { label: metrics.models.length > 1 ? i18n.t('chat.export.pdf.summary.models') : i18n.t('chat.export.pdf.summary.model'), value: resolveModelsValue(metrics.models) },
        { label: i18n.t('chat.export.pdf.summary.toolCalls'), value: String(metrics.toolCalls) },
        { label: i18n.t('chat.export.pdf.summary.created'), value: resolveTimestampValue(conversation.createdAt) },
        { label: i18n.t('chat.export.pdf.summary.updated'), value: resolveTimestampValue(conversation.updatedAt) },
        { label: i18n.t('chat.export.pdf.summary.span'), value: resolveSpanValue(conversation) },
        { label: i18n.t('chat.export.pdf.summary.compactions'), value: String(compactions) }
    ];
    if (metrics.tokens > 0) {
        items.push({ label: i18n.t('chat.export.pdf.summary.tokensUsed'), value: String(metrics.tokens) });
        items.push({ label: i18n.t('chat.export.pdf.summary.promptCompletion'), value: resolvePromptCompletionValue(metrics) });
    }
    if (metrics.characters > 0) {
        items.push({ label: i18n.t('chat.export.pdf.summary.words'), value: String(metrics.words) });
        items.push({ label: i18n.t('chat.export.pdf.summary.characters'), value: String(metrics.characters) });
    }
    items.push({ label: i18n.t('chat.export.pdf.summary.exported'), value: formatTimestamp(exportedAt.getTime()) });
    items.push({ label: i18n.t('chat.export.pdf.summary.conversationId'), value: isNonEmptyString(conversation.id) ? conversation.id : notAvailableValue() });
    return items;
};

export { buildCoverSummaryItems };
export type { ConversationExportModelCategory, ConversationExportModelDescriptor, ConversationExportModelResolver, ConversationExportSummaryItem };
