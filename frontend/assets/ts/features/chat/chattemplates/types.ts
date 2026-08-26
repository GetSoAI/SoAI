/* SoAI - Chat template contracts [frontend/assets/ts/features/chat/chattemplates/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SanitizerApi } from '@core/pagecontext/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { ChatConversationTerminalIndicator } from '@core/chat/protocols.ts';
import type { ConversationExecutionStatus } from '@features/chat/conversationExecutionState.ts';

type ConversationListAttentionStatus = 'none' | 'agent_plan_unseen';

type ConversationListItemBase = {
    id: string;
    titleHtml: string;
    titleLabel: string;
    dateLabel: string;
    messageLabel: string;
    isActive?: boolean;
    executionStatus?: ConversationExecutionStatus;
    attentionStatus?: ConversationListAttentionStatus;
    terminalIndicator?: ChatConversationTerminalIndicator | null | undefined;
    isAutomation?: boolean;
    isMessaging?: boolean;
    color?: string | null | undefined;
    colorTitle?: string | undefined;
    isFavorite?: boolean;
    isSelected?: boolean;
    deleteDisabled?: boolean;
    deleteTitle?: string | undefined;
};

type ConversationListItemRenaming = ConversationListItemBase & {
    isRenaming: true;
    titleEditorHtml: string;
};

type ConversationListItemDefault = ConversationListItemBase & {
    isRenaming?: false | undefined;
    titleEditorHtml?: string | undefined;
};

type ConversationListItem = ConversationListItemRenaming | ConversationListItemDefault;

interface ConversationListOptions {
    items: ConversationListItem[];
    deleteIconHtml: TrustedHtml;
    deleteTitle?: string;
    renameSaveIconHtml: TrustedHtml;
    renameSaveTitle?: string;
    renameCancelIconHtml: TrustedHtml;
    renameCancelTitle?: string;
    colorPickerIconHtml: TrustedHtml;
    colorPickerTitle?: string;
    automationIconHtml?: TrustedHtml;
    automationTitle?: string;
    messagingIconHtml?: TrustedHtml;
    messagingTitle?: string;
    sanitizer: SanitizerApi;
}

export type { ConversationListItem, ConversationListOptions };
