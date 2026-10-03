/* SoAI - Shared chat conversation authority lock [frontend/assets/ts/core/chat/conversationAuthorityLock.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { syncAttributeValue } from '@core/dom/patching.ts';
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
    unlockedToggleDisabled: boolean;
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
    const toggleDisabled = state.lock !== null || state.unlockedToggleDisabled;
    syncAttributeValue(button, SETTINGS_AUTHORITY_LOCK_ATTRIBUTE, state.lock?.authorityType ?? null);
    syncAttributeValue(button, 'aria-disabled', toggleDisabled ? 'true' : null);
    syncAttributeValue(button, 'data-toggle-disabled', toggleDisabled ? 'true' : null);
    button.disabled = state.lock === null && state.unlockedDisabled;
    syncAttributeValue(button, 'aria-label', state.lock === null ? state.unlockedAriaLabel : resolveAuthorityLockedControlLabel(state.lock, state.actionLabel));
    setTooltipText(button, state.lock === null ? state.unlockedTooltip : state.lock.reason);
};

export { applyAuthorityLockedButtonState, isConversationAuthorityLocked, renderAuthorityLockMarkupAttributes, resolveAuthorityLockedControlLabel, resolveAuthorityLockedControlLabels, resolveConversationAuthorityLock, SETTINGS_AUTHORITY_LOCK_ATTRIBUTE };
export type { AuthorityLockedButtonState, ConversationAuthorityControlLabels, ConversationAuthorityLock, ConversationAuthorityLockCandidate, ManagedConversationAuthorityType };
