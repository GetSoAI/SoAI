/* SoAI - WebWorker entrypoint for chat message rendering [frontend/assets/ts/features/chat/messagerenderworker/worker.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { WorkerMessage, WorkerResources } from '@features/chat/messagerenderworker/protocol.ts';
import { ChatMessageWorkerRenderer } from '@features/chat/messagerenderworker/renderer.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isObject, isString } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { setLanguageRuntime } from '@core/languageservice/runtime.ts';
import { formatLocalizedDate, formatLocalizedNumber, setLocalizationSnapshot } from '@core/localization/public.ts';
import { interpolateTranslationTemplate } from '@features/chat/messagerenderworker/translationInterpolation.ts';
import { decodeWorkerRequest, type DecodedWorkerRequest } from '@features/chat/messagerenderworker/workerRequestDecoding.ts';
import { WorkerTimelineIndexStateCache } from '@features/chat/messagerenderworker/workerTimelineIndexStateCache.ts';

let timelineIndexStateCache: WorkerTimelineIndexStateCache | null = null;
let messageRenderer: ChatMessageWorkerRenderer | null = null;

const post = (message: WorkerMessage): void => {
    const scope = globalThis;
    if (!(scope && typeof scope.postMessage === 'function')) {
        throw new Error('Chat render worker missing postMessage');
    }
    scope.postMessage(message);
};

const setWorkerLanguageRuntime = (workerResources: WorkerResources): void => {
    setLocalizationSnapshot(workerResources.localizationSnapshot, { dispatch: false });
    setLanguageRuntime({
        t: (key: string, parameters?: Record<string, JsonValue | null | undefined>): string => {
            const template = workerResources.translationsByKey[key];
            if (typeof template !== 'string' || !template) {
                throw new Error(`Chat render worker missing translation key: ${key}`);
            }
            return interpolateTranslationTemplate(template, parameters ?? null);
        },
        plural: (key: string, count: number, parameters?: Record<string, JsonValue | null | undefined>): string => {
            const resolvedKey = `${key}.${count === 1 ? 'singular' : 'plural'}`;
            const template = workerResources.translationsByKey[resolvedKey] ?? '';
            return interpolateTranslationTemplate(template, { ...(parameters ?? {}), count }) || '';
        },
        formatNumber: (value: number, options: Intl.NumberFormatOptions = {}): string => {
            return formatLocalizedNumber(value, options);
        },
        formatDate: (date: Date, options: Intl.DateTimeFormatOptions = {}): string => {
            return formatLocalizedDate(date, options);
        }
    });
};

const renderDecodedRequest = (decoded: DecodedWorkerRequest): void => {
    if (decoded.type === 'initResources') {
        const nextRenderer = new ChatMessageWorkerRenderer(decoded.resources);
        const nextTimelineIndexStateCache = new WorkerTimelineIndexStateCache();
        setWorkerLanguageRuntime(decoded.resources);
        timelineIndexStateCache = nextTimelineIndexStateCache;
        messageRenderer = nextRenderer;
        post({ type: 'ok', requestId: decoded.requestId });
        return;
    }

    const cache = timelineIndexStateCache;
    if (!cache) {
        throw new Error('Chat render worker not initialized (missing timeline index state cache)');
    }
    const renderer = messageRenderer;
    if (!renderer) {
        throw new Error('Chat render worker not initialized (missing message renderer)');
    }

    if (decoded.type === 'renderAssistantBodyFromMessage') {
        const timelineIndexState = cache.requireState(decoded.context);
        const html = renderer.renderAssistantBodyFromMessageHtml({
            isRichTextEnabled: decoded.isRichTextEnabled,
            codeRecognitionEnabled: decoded.codeRecognitionEnabled,
            isThinkingFeatureEnabled: decoded.isThinkingFeatureEnabled,
            isShowActivitiesEnabled: decoded.isShowActivitiesEnabled,
            activityDurationDisplayMode: decoded.activityDurationDisplayMode,
            isCurrentConversationExecuting: decoded.isCurrentConversationExecuting,
            canonicalPlan: decoded.canonicalPlan,
            suppressAssistantActivityWidgets: decoded.suppressAssistantActivityWidgets,
            nowMs: decoded.nowMs,
            message: decoded.message,
            timelineIndexState
        });
        post({ type: 'rendered', requestId: decoded.requestId, html, context: decoded.context });
        return;
    }

    const timelineIndexState = cache.requireState(decoded.context);
    const html = renderer.renderInlineDetailsFromMessageHtml({
        isRichTextEnabled: decoded.isRichTextEnabled,
        codeRecognitionEnabled: decoded.codeRecognitionEnabled,
        isThinkingFeatureEnabled: decoded.isThinkingFeatureEnabled,
        isShowActivitiesEnabled: decoded.isShowActivitiesEnabled,
        activityDurationDisplayMode: decoded.activityDurationDisplayMode,
        isCurrentConversationExecuting: decoded.isCurrentConversationExecuting,
        canonicalPlan: decoded.canonicalPlan,
        nowMs: decoded.nowMs,
        expectedType: decoded.expectedType,
        callId: decoded.callId,
        timelineSequenceIndex: decoded.timelineSequenceIndex,
        message: decoded.message,
        timelineIndexState
    });
    post({ type: 'rendered', requestId: decoded.requestId, html, context: decoded.context });
};

const onMessage = (event: MessageEvent): void => {
    const candidate: JsonValue | null | undefined = event.data;
    const requestId = isObject(candidate) && 'requestId' in candidate && isString(candidate['requestId']) ? candidate['requestId'] : '';
    try {
        renderDecodedRequest(decodeWorkerRequest(candidate));
    } catch (error) {
        const runtimeError = ensureError(error);
        const message = runtimeError.message || 'Chat render worker failed';
        post({ type: 'error', requestId, message, details: { error: message, stack: runtimeError.stack ?? null } });
    }
};

globalThis.onmessage = onMessage;
post({ type: 'ready' });
