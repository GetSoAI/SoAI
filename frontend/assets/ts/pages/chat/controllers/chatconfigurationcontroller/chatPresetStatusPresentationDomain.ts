/* SoAI - Chat preset library status presentation [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/chatPresetStatusPresentationDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { createCollectionNoticeAction, renderCollectionEmptyState, renderCollectionNotice, type CollectionNotice } from '@core/ui/collectionFeedback.ts';
import { CHAT_ACTIONS } from '@features/chat/public.ts';
import type { ChatPresetLibraryViewState } from '@pages/chat/controllers/chatconfigurationcontroller/contracts.ts';

const createStatusAction = (status: HTMLElement, action: string, label: string): HTMLButtonElement => {
    const button = createCollectionNoticeAction(status.ownerDocument, action, label);
    button.dataset['presetBaseDisabled'] = 'false';
    return button;
};

const resolveStatusPresentation = (state: ChatPresetLibraryViewState, status: HTMLElement): CollectionNotice | null => {
    if (state.phase === 'error' && state.lastSuccessAtMs === null) return { tone: 'error', title: i18n.t('chat.configuration.presetLibrary.status.errorTitle'), detail: i18n.t('chat.configuration.presetLibrary.loadFailed'), actions: [] };
    if (state.structurallyInvalidCount > 0) return { tone: 'warning', title: i18n.t('chat.configuration.presetLibrary.status.recoveryTitle'), detail: i18n.t('chat.configuration.presetLibrary.structurallyInvalid', { count: state.structurallyInvalidCount }), actions: [createStatusAction(status, CHAT_ACTIONS.RESET_PRESETS, i18n.t('chat.configuration.presetLibrary.resetAction'))] };
    return null;
};

const renderChatPresetStatus = (state: ChatPresetLibraryViewState, visibleRecordCount: number, status: HTMLElement, empty: HTMLElement): void => {
    const knownSnapshot = state.phase === 'ready' || state.lastSuccessAtMs !== null;
    const emptyLibrary = state.records.length === 0;
    renderCollectionEmptyState(
        empty,
        knownSnapshot && !state.editor && visibleRecordCount === 0
            ? {
                  icon: emptyLibrary ? 'save' : 'search',
                  title: emptyLibrary ? i18n.t('chat.configuration.presetLibrary.status.emptyTitle') : i18n.t('chat.configuration.presetLibrary.status.noMatchesTitle'),
                  message: emptyLibrary ? i18n.t('chat.configuration.presetLibrary.status.emptyDetail') : i18n.t('chat.configuration.presetLibrary.noMatches')
              }
            : null
    );
    renderCollectionNotice(status, resolveStatusPresentation(state, status));
};

export { renderChatPresetStatus };
