/* SoAI - Chat preset library status presentation [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/chatPresetStatusPresentationDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { formatDateTime } from '@core/primitives/dateTime.ts';
import { i18n } from '@core/i18n/index.ts';
import { createIconSlot } from '@core/ui/icons/view.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { CHAT_ACTIONS } from '@features/chat/public.ts';
import type { ChatPresetLibraryViewState } from '@pages/chat/controllers/chatconfigurationcontroller/contracts.ts';

type StatusPresentation = Readonly<{ modifier: string; icon: IconName | null; title: string; detail: string | null; action: 'refresh' | 'reset' | null }>;

const resolveStatusPresentation = (state: ChatPresetLibraryViewState, visibleRecordCount: number): StatusPresentation | null => {
    if (state.phase === 'loading' && state.records.length === 0) return { modifier: 'loading', icon: null, title: i18n.t('chat.configuration.presetLibrary.status.loadingTitle'), detail: i18n.t('chat.configuration.presetLibrary.status.loadingDetail'), action: null };
    if (state.phase === 'error' && state.records.length === 0) return { modifier: 'error', icon: 'error', title: i18n.t('chat.configuration.presetLibrary.status.errorTitle'), detail: i18n.t('chat.configuration.presetLibrary.loadFailed'), action: 'refresh' };
    if (state.stale) return { modifier: 'warning', icon: 'warning', title: i18n.t('chat.configuration.presetLibrary.status.staleTitle'), detail: i18n.t('chat.configuration.presetLibrary.stale', { value: state.lastSuccessAtMs === null ? i18n.t('common.notAvailable') : formatDateTime(state.lastSuccessAtMs, false) }), action: 'refresh' };
    if (state.structurallyInvalidCount > 0) return { modifier: 'warning', icon: 'warning', title: i18n.t('chat.configuration.presetLibrary.status.recoveryTitle'), detail: i18n.t('chat.configuration.presetLibrary.structurallyInvalid', { count: state.structurallyInvalidCount }), action: 'reset' };
    if (state.editor) return null;
    if (state.records.length === 0) return { modifier: 'empty', icon: 'save', title: i18n.t('chat.configuration.presetLibrary.status.emptyTitle'), detail: i18n.t('chat.configuration.presetLibrary.status.emptyDetail'), action: null };
    if (visibleRecordCount === 0) return { modifier: 'empty', icon: 'search', title: i18n.t('chat.configuration.presetLibrary.status.noMatchesTitle'), detail: i18n.t('chat.configuration.presetLibrary.noMatches'), action: null };
    return null;
};

const createStatusAction = (status: HTMLElement, action: string, label: string): HTMLButtonElement => {
    const button = status.ownerDocument.createElement('button');
    button.type = 'button';
    button.className = 'ui-button ui-button--sm';
    button.dataset['action'] = action;
    button.dataset['presetBaseDisabled'] = 'false';
    button.setAttribute('aria-label', label);
    button.dataset['tooltip'] = label;
    button.textContent = label;
    return button;
};

const renderChatPresetStatus = (state: ChatPresetLibraryViewState, visibleRecordCount: number, status: HTMLElement): void => {
    const presentation = resolveStatusPresentation(state, visibleRecordCount);
    status.replaceChildren();
    status.className = `chat-preset-status glass-surface-medium${presentation ? ` chat-preset-status--${presentation.modifier}` : ' u-hidden'}`;
    if (!presentation) return;
    const indicator = presentation.icon ? createIconSlot(status.ownerDocument, getIconSync(presentation.icon, { size: 20, strokeWidth: 1.7 }), { className: 'chat-preset-status-icon' }) : status.ownerDocument.createElement('span');
    if (!presentation.icon) {
        indicator.className = 'loading-spinner chat-preset-status-spinner';
        indicator.setAttribute('aria-hidden', 'true');
    }
    const copy = status.ownerDocument.createElement('div');
    copy.className = 'chat-preset-status-copy';
    const title = status.ownerDocument.createElement('strong');
    title.textContent = presentation.title;
    copy.append(title);
    if (presentation.detail) {
        const detail = status.ownerDocument.createElement('span');
        detail.textContent = presentation.detail;
        copy.append(detail);
    }
    status.append(indicator, copy);
    if (presentation.action === 'refresh') status.append(createStatusAction(status, CHAT_ACTIONS.REFRESH_PRESETS, i18n.t('chat.configuration.presetLibrary.retryAction')));
    if (presentation.action === 'reset') status.append(createStatusAction(status, CHAT_ACTIONS.RESET_PRESETS, i18n.t('chat.configuration.presetLibrary.resetAction')));
};

export { renderChatPresetStatus };
