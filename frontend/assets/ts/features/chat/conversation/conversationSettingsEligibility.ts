/* SoAI - Chat feature conversation settings eligibility [frontend/assets/ts/features/chat/conversation/conversationSettingsEligibility.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationSettingsAuthorityEligibility } from '@core/chat/conversationSettingsAuthority.ts';

type ConversationSettingsCandidate = {
    id?: string;
    isAutomation?: boolean;
    settingsAuthority?: ConversationSettingsAuthorityEligibility;
};

type AutomationConversationSettingsCandidate = ConversationSettingsCandidate & {
    settingsAuthority: {
        type: 'automation';
        readOnly: true;
    };
};

type MessagingAccountConversationSettingsCandidate = ConversationSettingsCandidate & {
    settingsAuthority: {
        type: 'messaging_account';
        readOnly: true;
    };
};

type WritableConversationSettingsCandidate = ConversationSettingsCandidate & {
    settingsAuthority: {
        type: 'conversation';
        readOnly: false;
    };
};

type PersistedConversationSettingsCandidate = ConversationSettingsCandidate & {
    id: string;
};

const isAutomationConversation = <ConversationType extends ConversationSettingsCandidate>(conversation: ConversationType | null): conversation is ConversationType & AutomationConversationSettingsCandidate => {
    return conversation !== null && conversation.settingsAuthority?.type === 'automation' && conversation.settingsAuthority.readOnly === true;
};

const isMessagingAccountConversation = <ConversationType extends ConversationSettingsCandidate>(conversation: ConversationType | null): conversation is ConversationType & MessagingAccountConversationSettingsCandidate => {
    return conversation !== null && conversation.settingsAuthority?.type === 'messaging_account' && conversation.settingsAuthority.readOnly === true;
};

const isChatConversationSettingsWritable = <ConversationType extends ConversationSettingsCandidate>(conversation: ConversationType | null): conversation is ConversationType & WritableConversationSettingsCandidate => {
    return conversation !== null && conversation.settingsAuthority?.type === 'conversation' && conversation.settingsAuthority.readOnly === false;
};

const canInteractivelyAdjustConversationTools = <ConversationType extends ConversationSettingsCandidate>(conversation: ConversationType | null): conversation is ConversationType & PersistedConversationSettingsCandidate => {
    return conversation !== null && typeof conversation.id === 'string' && conversation.id.trim().length > 0;
};

export { canInteractivelyAdjustConversationTools, isAutomationConversation, isChatConversationSettingsWritable, isMessagingAccountConversation };
