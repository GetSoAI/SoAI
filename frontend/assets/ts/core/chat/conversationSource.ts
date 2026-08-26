/* SoAI - Conversation source metadata contract [frontend/assets/ts/core/chat/conversationSource.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { readNullableTrimmedStringValue, readRequiredBooleanValue } from '@core/types/payloadValueReaders.ts';

type MessagingPlatform = 'telegram' | 'whatsapp' | 'discord';

type ConversationSource = {
    isMessaging: boolean;
    messagingPlatform: MessagingPlatform | null;
    messagingAccountLabel: string | null;
    messagingAccountSnapshotId: string | null;
};

const readMessagingPlatform = (value: JsonValue | undefined, label: string): MessagingPlatform | null => {
    if (value === null) return null;
    if (value === 'telegram' || value === 'whatsapp' || value === 'discord') return value;
    throw new TypeError(`${label} is invalid`);
};

const decodeConversationSource = (record: JsonObject, label: string): ConversationSource => {
    const source: ConversationSource = {
        isMessaging: readRequiredBooleanValue(record['is_messaging'], `${label}.is_messaging`),
        messagingPlatform: readMessagingPlatform(record['messaging_platform'], `${label}.messaging_platform`),
        messagingAccountLabel: readNullableTrimmedStringValue(record['messaging_account_label'], `${label}.messaging_account_label`),
        messagingAccountSnapshotId: readNullableTrimmedStringValue(record['messaging_account_snapshot_id'], `${label}.messaging_account_snapshot_id`)
    };
    const completeMessagingIdentity = source.messagingPlatform !== null && source.messagingAccountLabel !== null && source.messagingAccountSnapshotId !== null;
    const emptyMessagingIdentity = source.messagingPlatform === null && source.messagingAccountLabel === null && source.messagingAccountSnapshotId === null;
    if ((source.isMessaging && !completeMessagingIdentity) || (!source.isMessaging && !emptyMessagingIdentity)) {
        throw new TypeError(`${label} messaging identity is inconsistent`);
    }
    return source;
};

export { decodeConversationSource, readMessagingPlatform };
export type { ConversationSource, MessagingPlatform };
