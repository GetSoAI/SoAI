/* SoAI - Settings page control layer users manager WebUI sessions [frontend/assets/ts/pages/settings/controllers/usersmanager/WebuiSessions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { WebuiSession } from '@core/api/contracts/webuiSessionContracts.ts';
import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatDateTime } from '@core/primitives/dateTime.ts';
import { renderLabelAttributes } from '@core/security/public.ts';
import { escapeAttribute, escapeHtml } from '@core/security/textSanitizer.ts';
import { renderControlDisabledAttributes } from '@core/ui/controls/disabledState.ts';
import { renderEmptyState } from '@core/ui/emptyState.ts';

const SESSIONS_ACTION_REVOKE = 'settings-sessions-revoke';
const SESSIONS_ACTION_REVOKE_ALL = 'settings-sessions-revoke-all';

type SessionsActionId = typeof SESSIONS_ACTION_REVOKE | typeof SESSIONS_ACTION_REVOKE_ALL;

const { guard: isSessionsActionId } = createActionIdSet<SessionsActionId>(SESSIONS_ACTION_REVOKE, SESSIONS_ACTION_REVOKE_ALL);

const renderRevokeAllItem = (loading: boolean): string => {
    const title = i18n.t('settings.users.sessions.revokeAll.title');
    const description = i18n.t('settings.users.sessions.revokeAll.description');
    const buttonLabel = i18n.t('settings.users.sessions.revokeAll.button');
    return `<div id="webui-sessions-revoke-all-item" class="settings-record-item settings-record-item--session"><div class="settings-record-info"><div class="settings-record-header"><span class="settings-record-label">${escapeHtml(title)}</span></div><div class="settings-record-meta"><span>${escapeHtml(description)}</span></div></div><div class="settings-record-actions"><button type="button" id="webui-sessions-revoke-all-btn" class="ui-button ui-button--sm ui-variant-danger" data-action="${SESSIONS_ACTION_REVOKE_ALL}" ${renderLabelAttributes(buttonLabel)}${renderControlDisabledAttributes(loading)}>${escapeHtml(buttonLabel)}</button></div></div>`;
};

const renderSessionItem = (session: WebuiSession): string => {
    const label = escapeHtml(session.deviceLabel);
    const clientType = session.clientType === 'android' ? i18n.t('settings.users.sessions.clientTypes.android') : i18n.t('settings.users.sessions.clientTypes.web');
    const currentBadge = session.current ? `<span class="settings-record-badge settings-record-badge--active">${i18n.t('settings.users.sessions.current')}</span>` : '';
    const userAgent = session.userAgent ? escapeHtml(session.userAgent) : i18n.t('common.notAvailable');
    const lastSeen = formatDateTime(session.lastSeenAtMs, false);
    const created = formatDateTime(session.createdAtMs, false);
    const revokeLabel = session.current ? i18n.t('header.menu.logout') : i18n.t('settings.users.sessions.revoke');
    return `<div class="settings-record-item settings-record-item--session"><div class="settings-record-info"><div class="settings-record-header"><span class="settings-record-label">${label}</span>${currentBadge}</div><div class="settings-record-meta"><span>${escapeHtml(clientType)}</span><span>${escapeHtml(i18n.t('settings.users.sessions.lastSeen', { value: lastSeen }))}</span><span>${escapeHtml(i18n.t('settings.users.sessions.created', { value: created }))}</span><span>${userAgent}</span></div></div><div class="settings-record-actions"><button type="button" class="ui-button ui-button--sm ${session.current ? 'ui-variant-neutral' : 'ui-variant-danger'}" data-action="${SESSIONS_ACTION_REVOKE}" data-jti="${escapeAttribute(session.jti)}" data-current="${session.current ? 'true' : 'false'}" ${renderLabelAttributes(revokeLabel)}>${revokeLabel}</button></div></div>`;
};

const renderSessionsContent = (sessions: readonly WebuiSession[] | null): string => {
    const revokeAllItem = renderRevokeAllItem(sessions === null);
    if (sessions === null) {
        return `${revokeAllItem}${renderEmptyState({ title: i18n.t('common.loading'), className: 'ui-empty-state--simple' }).html}`;
    }
    const sessionsContent = sessions.length > 0 ? sessions.map(renderSessionItem).join('') : renderEmptyState({ title: i18n.t('settings.users.sessions.empty'), className: 'ui-empty-state--simple' }).html;
    return `${revokeAllItem}${sessionsContent}`;
};

export { isSessionsActionId, renderSessionsContent, SESSIONS_ACTION_REVOKE, SESSIONS_ACTION_REVOKE_ALL };
export type { SessionsActionId };
