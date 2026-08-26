/* SoAI - Conversation export origin label resolution [frontend/assets/ts/features/chat/conversationexport/conversationOrigin.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { MessagingPlatform } from '@core/chat/conversationSource.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import type { ConversationContract } from '@features/chat/ChatTypes.ts';
import { isAutomationConversation, isMessagingAccountConversation } from '@features/chat/conversation/conversationSettingsEligibility.ts';
import { clampCoverFieldText, COVER_ORIGIN_MAX_LENGTH } from '@features/chat/conversationexport/coverContract.ts';

const messagingPlatformLabel = (platform: MessagingPlatform | null | undefined): string => {
    switch (platform) {
        case 'telegram':
            return i18n.t('chat.export.pdf.origin.platform.telegram');
        case 'whatsapp':
            return i18n.t('chat.export.pdf.origin.platform.whatsapp');
        case 'discord':
            return i18n.t('chat.export.pdf.origin.platform.discord');
        case null:
        case undefined:
            return i18n.t('chat.export.pdf.origin.platform.unknown');
    }
};

const resolveConversationExportOriginLabel = (conversation: ConversationContract): string => {
    const entityLabel = toTrimmedStringOrNull(conversation.settingsAuthority?.entityLabel);
    if (isMessagingAccountConversation(conversation)) {
        const platform = messagingPlatformLabel(conversation.messagingPlatform);
        const origin = entityLabel === null ? platform : i18n.t('chat.export.pdf.origin.messaging', { platform, account: entityLabel });
        return clampCoverFieldText(origin, COVER_ORIGIN_MAX_LENGTH);
    }
    if (isAutomationConversation(conversation) && entityLabel !== null) {
        return clampCoverFieldText(i18n.t('chat.export.pdf.origin.automation', { name: entityLabel }), COVER_ORIGIN_MAX_LENGTH);
    }
    return '';
};

export { resolveConversationExportOriginLabel };
