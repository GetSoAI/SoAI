/* SoAI - Chat feature assistant activity widget footer [frontend/assets/ts/features/chat/message/messageview/assistantActivityWidgetFooter.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatPositiveEpochMsWithFallback } from '@core/primitives/dateTime.ts';
import type { ChatMessageRenderHost } from '@features/chat/message/messageview/types.ts';

const REQUESTED_AT_OPTIONS: Readonly<Intl.DateTimeFormatOptions> = Object.freeze({
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit'
});

const formatActivityWidgetRequestedAt = (startedAtMs: number | undefined): string => {
    const fallback = i18n.t('common.notAvailableShort');
    const timestamp = formatPositiveEpochMsWithFallback(startedAtMs, fallback, REQUESTED_AT_OPTIONS);
    return i18n.t('chat.activityWidgets.requestedAt', { time: timestamp });
};

const renderAssistantActivityWidgetFooter = (host: ChatMessageRenderHost, startedAtMs: number | undefined): string => {
    const requestedAt = host.escapeHtml(formatActivityWidgetRequestedAt(startedAtMs));
    return ['<footer class="assistant-activity-widget__footer">', `<span class="assistant-activity-widget__requested-at">${requestedAt}</span>`, '<img class="assistant-activity-widget__brand-logo logo logo-small logo-transition" data-logo-type="small" alt="" aria-hidden="true" loading="lazy" decoding="async">', '</footer>'].join('');
};

export { renderAssistantActivityWidgetFooter };
