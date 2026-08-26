/* SoAI - Chat feature message translations [frontend/assets/ts/features/chat/message/messageview/chatMessageTranslations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { i18n } from '@core/i18n/index.ts';
import { buildSyntaxHighlighterLanguageTranslations } from '@core/syntaxhighlighter/service.ts';
import type { ChatMessageTranslationKey, ChatMessageWorkerTranslationKey } from '@features/chat/message/messageview/types.ts';

const translateChatMessage = (key: ChatMessageTranslationKey, parameters?: Record<string, JsonValue>): string => {
    switch (key) {
        case 'chat.comparison.navigation.next':
            return i18n.t('chat.comparison.navigation.next', parameters);
        case 'chat.comparison.navigation.previous':
            return i18n.t('chat.comparison.navigation.previous', parameters);
        case 'chat.loading.label':
            return i18n.t('chat.loading.label', parameters);
        case 'chat.loading.modelPreview':
            return i18n.t('chat.loading.modelPreview', parameters);
        case 'chat.attachments.badge.attachment':
            return i18n.t('chat.attachments.badge.attachment', parameters);
        case 'chat.attachments.badge.knowledge':
            return i18n.t('chat.attachments.badge.knowledge', parameters);
        case 'chat.attachments.badge.soaiLink':
            return i18n.t('chat.attachments.badge.soaiLink', parameters);
        case 'chat.attachments.openAttachment':
            return i18n.t('chat.attachments.openAttachment', parameters);
        case 'chat.attachments.openKnowledge':
            return i18n.t('chat.attachments.openKnowledge', parameters);
        case 'chat.attachments.openSoaiLink':
            return i18n.t('chat.attachments.openSoaiLink', parameters);
        case 'chat.message.actions.copyCode':
            return i18n.t('chat.message.actions.copyCode', parameters);
        case 'chat.message.actions.undoDelete':
            return i18n.t('chat.message.actions.undoDelete', parameters);
        case 'chat.message.deleted':
            return i18n.t('chat.message.deleted', parameters);
        case 'chat.message.generatedImage':
            return i18n.t('chat.message.generatedImage', parameters);
        case 'chat.message.renderFailed':
            return i18n.t('chat.message.renderFailed', parameters);
        case 'chat.message.toolCall':
            return i18n.t('chat.message.toolCall', parameters);
        case 'chat.notifications.requestCancelled':
            return i18n.t('chat.notifications.requestCancelled', parameters);
        case 'chat.processing.label':
            return i18n.t('chat.processing.label', parameters);
        case 'chat.thinking.label':
            return i18n.t('chat.thinking.label', parameters);
        case 'chat.activityWidgets.requestedAt':
            return i18n.t('chat.activityWidgets.requestedAt', parameters);
        case 'chat.news.articleCount':
            return i18n.t('chat.news.articleCount', parameters);
        case 'chat.news.articles':
            return i18n.t('chat.news.articles', parameters);
        case 'chat.news.label':
            return i18n.t('chat.news.label', parameters);
        case 'chat.news.noImage':
            return i18n.t('chat.news.noImage', parameters);
        case 'chat.news.readFullArticle':
            return i18n.t('chat.news.readFullArticle', parameters);
        case 'chat.agent.plan.viewPlan':
            return i18n.t('chat.agent.plan.viewPlan', parameters);
        case 'chat.planWidget.execute':
            return i18n.t('chat.planWidget.execute', parameters);
        case 'chat.planWidget.label':
            return i18n.t('chat.planWidget.label', parameters);
        case 'chat.planWidget.metrics':
            return i18n.t('chat.planWidget.metrics', parameters);
        case 'chat.planWidget.revision':
            return i18n.t('chat.planWidget.revision', parameters);
        case 'chat.weather.clouds':
            return i18n.t('chat.weather.clouds', parameters);
        case 'chat.weather.compass.e':
            return i18n.t('chat.weather.compass.e', parameters);
        case 'chat.weather.compass.n':
            return i18n.t('chat.weather.compass.n', parameters);
        case 'chat.weather.compass.ne':
            return i18n.t('chat.weather.compass.ne', parameters);
        case 'chat.weather.compass.nw':
            return i18n.t('chat.weather.compass.nw', parameters);
        case 'chat.weather.compass.s':
            return i18n.t('chat.weather.compass.s', parameters);
        case 'chat.weather.compass.se':
            return i18n.t('chat.weather.compass.se', parameters);
        case 'chat.weather.compass.sw':
            return i18n.t('chat.weather.compass.sw', parameters);
        case 'chat.weather.compass.w':
            return i18n.t('chat.weather.compass.w', parameters);
        case 'chat.weather.feelsLike':
            return i18n.t('chat.weather.feelsLike', parameters);
        case 'chat.weather.forecast':
            return i18n.t('chat.weather.forecast', parameters);
        case 'chat.weather.hourly':
            return i18n.t('chat.weather.hourly', parameters);
        case 'chat.weather.humidity':
            return i18n.t('chat.weather.humidity', parameters);
        case 'chat.weather.label':
            return i18n.t('chat.weather.label', parameters);
        case 'chat.weather.precipitation':
            return i18n.t('chat.weather.precipitation', parameters);
        case 'chat.weather.units.imperial':
            return i18n.t('chat.weather.units.imperial', parameters);
        case 'chat.weather.units.metric':
            return i18n.t('chat.weather.units.metric', parameters);
        case 'chat.weather.wind':
            return i18n.t('chat.weather.wind', parameters);
        case 'chat.toolActivity.codeDiff':
            return i18n.t('chat.toolActivity.codeDiff', parameters);
        case 'chat.toolActivity.compactionMetadata':
            return i18n.t('chat.toolActivity.compactionMetadata', parameters);
        case 'chat.toolActivity.compactionPrompt':
            return i18n.t('chat.toolActivity.compactionPrompt', parameters);
        case 'chat.toolActivity.compactionSummary':
            return i18n.t('chat.toolActivity.compactionSummary', parameters);
        case 'chat.toolActivity.removeCompactionBoundary':
            return i18n.t('chat.toolActivity.removeCompactionBoundary', parameters);
        case 'chat.toolActivity.stopShell':
            return i18n.t('chat.toolActivity.stopShell', parameters);
        case 'chat.toolActivity.stopShellHeader':
            return i18n.t('chat.toolActivity.stopShellHeader', parameters);
        case 'chat.toolActivity.diffTruncated':
            return i18n.t('chat.toolActivity.diffTruncated', parameters);
        case 'chat.toolActivity.error':
            return i18n.t('chat.toolActivity.error', parameters);
        case 'chat.toolActivity.fileView':
            return i18n.t('chat.toolActivity.fileView', parameters);
        case 'chat.toolActivity.fileViewPartial':
            return i18n.t('chat.toolActivity.fileViewPartial', parameters);
        case 'chat.toolActivity.request':
            return i18n.t('chat.toolActivity.request', parameters);
        case 'chat.toolActivity.result':
            return i18n.t('chat.toolActivity.result', parameters);
        case 'chat.toolActivity.screenshot':
            return i18n.t('chat.toolActivity.screenshot', parameters);
        case 'chat.toolActivity.image':
            return i18n.t('chat.toolActivity.image', parameters);
        case 'chat.toolActivity.video':
            return i18n.t('chat.toolActivity.video', parameters);
        case 'chat.toolActivity.videoFrames':
            return i18n.t('chat.toolActivity.videoFrames', parameters);
        case 'chat.toolActivity.transcript':
            return i18n.t('chat.toolActivity.transcript', parameters);
        case 'chat.toolActivity.status.completed':
            return i18n.t('chat.toolActivity.status.completed', parameters);
        case 'chat.toolActivity.status.error':
            return i18n.t('chat.toolActivity.status.error', parameters);
        case 'chat.toolActivity.status.pending':
            return i18n.t('chat.toolActivity.status.pending', parameters);
        case 'chat.toolActivity.status.running':
            return i18n.t('chat.toolActivity.status.running', parameters);
        case 'chat.toolActivity.subagentAdditionalContext':
            return i18n.t('chat.toolActivity.subagentAdditionalContext', parameters);
        case 'chat.toolActivity.subagentPrompt':
            return i18n.t('chat.toolActivity.subagentPrompt', parameters);
        case 'chat.toolActivity.subagentStatus':
            return i18n.t('chat.toolActivity.subagentStatus', parameters);
        case 'chat.toolActivity.subagentStream':
            return i18n.t('chat.toolActivity.subagentStream', parameters);
        case 'chat.toolActivity.truncatedChars':
            return i18n.t('chat.toolActivity.truncatedChars', parameters);
        case 'chat.toolActivity.viewFullOutput':
            return i18n.t('chat.toolActivity.viewFullOutput', parameters);
        case 'chat.waitForUser.label':
            return i18n.t('chat.waitForUser.label', parameters);
        case 'common.close':
            return i18n.t('common.close', parameters);
        case 'common.copy':
            return i18n.t('common.copy', parameters);
        case 'common.notAvailableShort':
            return i18n.t('common.notAvailableShort', parameters);
        case 'common.placeholders.emptyCodeBlock':
            return i18n.t('common.placeholders.emptyCodeBlock', parameters);
        case 'common.placeholders.plainTextCodeBlockLanguage':
            return i18n.t('common.placeholders.plainTextCodeBlockLanguage', parameters);
        case 'common.time.units.day.short':
            return i18n.t('common.time.units.day.short', parameters);
        case 'common.view':
            return i18n.t('common.view', parameters);
        case 'contentPreview.actions.openSource':
            return i18n.t('contentPreview.actions.openSource', parameters);
        case 'richText.footnotes.backToReference':
            return i18n.t('richText.footnotes.backToReference', parameters);
    }
    throw new Error(`Unknown chat message translation key: ${key}`);
};

const buildChatMessageWorkerTranslations = (): Record<ChatMessageWorkerTranslationKey, string> => {
    return {
        'chat.comparison.navigation.next': i18n.t('chat.comparison.navigation.next'),
        'chat.comparison.navigation.previous': i18n.t('chat.comparison.navigation.previous'),
        'chat.loading.label': i18n.t('chat.loading.label'),
        'chat.loading.modelPreview': i18n.t('chat.loading.modelPreview'),
        'chat.attachments.badge.attachment': i18n.t('chat.attachments.badge.attachment'),
        'chat.attachments.badge.knowledge': i18n.t('chat.attachments.badge.knowledge'),
        'chat.attachments.badge.soaiLink': i18n.t('chat.attachments.badge.soaiLink'),
        'chat.attachments.openAttachment': i18n.t('chat.attachments.openAttachment'),
        'chat.attachments.openKnowledge': i18n.t('chat.attachments.openKnowledge'),
        'chat.attachments.openSoaiLink': i18n.t('chat.attachments.openSoaiLink'),
        'chat.message.actions.copyCode': i18n.t('chat.message.actions.copyCode'),
        'chat.message.actions.undoDelete': i18n.t('chat.message.actions.undoDelete'),
        'chat.message.deleted': i18n.t('chat.message.deleted'),
        'chat.message.generatedImage': i18n.t('chat.message.generatedImage'),
        'chat.message.renderFailed': i18n.t('chat.message.renderFailed'),
        'chat.message.toolCall': i18n.t('chat.message.toolCall'),
        'chat.notifications.requestCancelled': i18n.t('chat.notifications.requestCancelled'),
        'chat.processing.label': i18n.t('chat.processing.label'),
        'chat.thinking.label': i18n.t('chat.thinking.label'),
        'chat.activityWidgets.requestedAt': i18n.t('chat.activityWidgets.requestedAt', { time: '{time}' }),
        'chat.news.articleCount': i18n.t('chat.news.articleCount', { count: '{count}' }),
        'chat.news.articles': i18n.t('chat.news.articles'),
        'chat.news.label': i18n.t('chat.news.label'),
        'chat.news.noImage': i18n.t('chat.news.noImage'),
        'chat.news.readFullArticle': i18n.t('chat.news.readFullArticle'),
        'chat.agent.plan.viewPlan': i18n.t('chat.agent.plan.viewPlan'),
        'chat.planWidget.execute': i18n.t('chat.planWidget.execute'),
        'chat.planWidget.label': i18n.t('chat.planWidget.label'),
        'chat.planWidget.metrics': i18n.t('chat.planWidget.metrics', { lines: '{lines}', characters: '{characters}' }),
        'chat.planWidget.revision': i18n.t('chat.planWidget.revision', { revision: '{revision}' }),
        'chat.weather.clouds': i18n.t('chat.weather.clouds'),
        'chat.weather.compass.e': i18n.t('chat.weather.compass.e'),
        'chat.weather.compass.n': i18n.t('chat.weather.compass.n'),
        'chat.weather.compass.ne': i18n.t('chat.weather.compass.ne'),
        'chat.weather.compass.nw': i18n.t('chat.weather.compass.nw'),
        'chat.weather.compass.s': i18n.t('chat.weather.compass.s'),
        'chat.weather.compass.se': i18n.t('chat.weather.compass.se'),
        'chat.weather.compass.sw': i18n.t('chat.weather.compass.sw'),
        'chat.weather.compass.w': i18n.t('chat.weather.compass.w'),
        'chat.weather.feelsLike': i18n.t('chat.weather.feelsLike'),
        'chat.weather.forecast': i18n.t('chat.weather.forecast'),
        'chat.weather.hourly': i18n.t('chat.weather.hourly'),
        'chat.weather.humidity': i18n.t('chat.weather.humidity'),
        'chat.weather.label': i18n.t('chat.weather.label'),
        'chat.weather.precipitation': i18n.t('chat.weather.precipitation'),
        'chat.weather.units.imperial': i18n.t('chat.weather.units.imperial'),
        'chat.weather.units.metric': i18n.t('chat.weather.units.metric'),
        'chat.weather.wind': i18n.t('chat.weather.wind'),
        'chat.toolActivity.codeDiff': i18n.t('chat.toolActivity.codeDiff'),
        'chat.toolActivity.compactionMetadata': i18n.t('chat.toolActivity.compactionMetadata'),
        'chat.toolActivity.compactionPrompt': i18n.t('chat.toolActivity.compactionPrompt'),
        'chat.toolActivity.compactionSummary': i18n.t('chat.toolActivity.compactionSummary'),
        'chat.toolActivity.removeCompactionBoundary': i18n.t('chat.toolActivity.removeCompactionBoundary'),
        'chat.toolActivity.stopShell': i18n.t('chat.toolActivity.stopShell'),
        'chat.toolActivity.stopShellHeader': i18n.t('chat.toolActivity.stopShellHeader'),
        'chat.toolActivity.diffTruncated': i18n.t('chat.toolActivity.diffTruncated'),
        'chat.toolActivity.error': i18n.t('chat.toolActivity.error'),
        'chat.toolActivity.fileView': i18n.t('chat.toolActivity.fileView'),
        'chat.toolActivity.fileViewPartial': i18n.t('chat.toolActivity.fileViewPartial'),
        'chat.toolActivity.request': i18n.t('chat.toolActivity.request'),
        'chat.toolActivity.result': i18n.t('chat.toolActivity.result'),
        'chat.toolActivity.screenshot': i18n.t('chat.toolActivity.screenshot'),
        'chat.toolActivity.image': i18n.t('chat.toolActivity.image'),
        'chat.toolActivity.video': i18n.t('chat.toolActivity.video'),
        'chat.toolActivity.videoFrames': i18n.t('chat.toolActivity.videoFrames'),
        'chat.toolActivity.transcript': i18n.t('chat.toolActivity.transcript'),
        'chat.toolActivity.status.completed': i18n.t('chat.toolActivity.status.completed'),
        'chat.toolActivity.status.error': i18n.t('chat.toolActivity.status.error'),
        'chat.toolActivity.status.pending': i18n.t('chat.toolActivity.status.pending'),
        'chat.toolActivity.status.running': i18n.t('chat.toolActivity.status.running'),
        'chat.toolActivity.subagentAdditionalContext': i18n.t('chat.toolActivity.subagentAdditionalContext'),
        'chat.toolActivity.subagentPrompt': i18n.t('chat.toolActivity.subagentPrompt'),
        'chat.toolActivity.subagentStatus': i18n.t('chat.toolActivity.subagentStatus'),
        'chat.toolActivity.subagentStream': i18n.t('chat.toolActivity.subagentStream'),
        'chat.toolActivity.truncatedChars': i18n.t('chat.toolActivity.truncatedChars', { count: '{count}' }),
        'chat.toolActivity.viewFullOutput': i18n.t('chat.toolActivity.viewFullOutput'),
        'chat.waitForUser.label': i18n.t('chat.waitForUser.label'),
        'common.close': i18n.t('common.close'),
        'common.copy': i18n.t('common.copy'),
        'common.notAvailableShort': i18n.t('common.notAvailableShort'),
        'common.placeholders.emptyCodeBlock': i18n.t('common.placeholders.emptyCodeBlock'),
        'common.placeholders.plainTextCodeBlockLanguage': i18n.t('common.placeholders.plainTextCodeBlockLanguage'),
        'common.time.units.day.short': i18n.t('common.time.units.day.short', { count: '{count}' }),
        'common.view': i18n.t('common.view'),
        'contentPreview.actions.openSource': i18n.t('contentPreview.actions.openSource'),
        'richText.footnotes.backToReference': i18n.t('richText.footnotes.backToReference'),
        ...buildSyntaxHighlighterLanguageTranslations()
    };
};

export { buildChatMessageWorkerTranslations, translateChatMessage };
