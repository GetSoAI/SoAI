/* SoAI - Shared chat conversation authority lock [frontend/assets/ts/core/chat/conversationAuthorityLock.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import type { ConversationSettingsAuthorityEligibility, ConversationSettingsAuthorityType } from '@core/chat/conversationSettingsAuthority.ts';

type ManagedConversationAuthorityType = Exclude<ConversationSettingsAuthorityType, 'conversation'>;

interface ConversationAuthorityLock {
    authorityType: ManagedConversationAuthorityType;
    reason: string;
}

interface ConversationAuthorityLockCandidate {
    settingsAuthority?: ConversationSettingsAuthorityEligibility;
}

interface ConversationAuthorityControlLabels {
    ariaLabel: string;
    tooltip: string;
}

interface AuthorityLockedButtonState {
    lock: ConversationAuthorityLock | null;
    actionLabel: string;
    unlockedAriaLabel: string;
    unlockedTooltip: string;
    unlockedDisabled: boolean;
}

const SETTINGS_AUTHORITY_LOCK_ATTRIBUTE = 'data-settings-authority-lock';

const resolveConversationAuthorityLock = (conversation: ConversationAuthorityLockCandidate | null): ConversationAuthorityLock | null => {
    const authorityType: ConversationSettingsAuthorityType = conversation?.settingsAuthority?.type ?? 'conversation';
    if (authorityType === 'conversation') {
        return null;
    }
    if (authorityType === 'automation') {
        return { authorityType: 'automation', reason: i18n.t('chat.authorityLock.automationReason') };
    }
    if (authorityType === 'messaging_account') {
        return { authorityType: 'messaging_account', reason: i18n.t('chat.authorityLock.messagingAccountReason') };
    }
    throw new TypeError(`Conversation settings authority type is unsupported: ${String(authorityType)}`);
};

const isConversationAuthorityLocked = (conversation: ConversationAuthorityLockCandidate | null): boolean => resolveConversationAuthorityLock(conversation) !== null;

const resolveAuthorityLockedControlLabel = (lock: ConversationAuthorityLock, actionLabel: string): string => i18n.t('chat.authorityLock.lockedControlLabel', { action: actionLabel, reason: lock.reason });

const resolveAuthorityLockedControlLabels = (lock: ConversationAuthorityLock | null, unlockedAriaLabel: string, unlockedTooltip: string): ConversationAuthorityControlLabels => {
    if (lock === null) {
        return { ariaLabel: unlockedAriaLabel, tooltip: unlockedTooltip };
    }
    return { ariaLabel: resolveAuthorityLockedControlLabel(lock, unlockedAriaLabel), tooltip: lock.reason };
};

const renderAuthorityLockMarkupAttributes = (lock: ConversationAuthorityLock | null): string => (lock === null ? '' : `aria-disabled="true" data-toggle-disabled="true" ${SETTINGS_AUTHORITY_LOCK_ATTRIBUTE}="${lock.authorityType}"`);

const applyAuthorityLockedButtonState = (button: HTMLButtonElement, state: AuthorityLockedButtonState): void => {
    if (state.lock === null) {
        delete button.dataset['settingsAuthorityLock'];
        button.removeAttribute('aria-disabled');
        delete button.dataset['toggleDisabled'];
        button.disabled = state.unlockedDisabled;
        button.setAttribute('aria-label', state.unlockedAriaLabel);
        setTooltipText(button, state.unlockedTooltip);
        return;
    }
    button.dataset['settingsAuthorityLock'] = state.lock.authorityType;
    button.setAttribute('aria-disabled', 'true');
    button.dataset['toggleDisabled'] = 'true';
    button.disabled = false;
    button.setAttribute('aria-label', resolveAuthorityLockedControlLabel(state.lock, state.actionLabel));
    setTooltipText(button, state.lock.reason);
};

export { applyAuthorityLockedButtonState, isConversationAuthorityLocked, renderAuthorityLockMarkupAttributes, resolveAuthorityLockedControlLabel, resolveAuthorityLockedControlLabels, resolveConversationAuthorityLock, SETTINGS_AUTHORITY_LOCK_ATTRIBUTE };
export type { AuthorityLockedButtonState, ConversationAuthorityControlLabels, ConversationAuthorityLock, ConversationAuthorityLockCandidate, ManagedConversationAuthorityType };
