/* SoAI - Conversation settings authority contract [frontend/assets/ts/core/chat/conversationSettingsAuthority.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredBooleanValue, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';

type ConversationSettingsAuthorityType = 'conversation' | 'automation' | 'messaging_account';

type ConversationSettingsAuthority = {
    type: ConversationSettingsAuthorityType;
    entityId: string;
    entityLabel: string;
    readOnly: boolean;
};

type ConversationSettingsAuthorityEligibility = Pick<ConversationSettingsAuthority, 'type' | 'readOnly'>;

const decodeConversationSettingsAuthority = (value: JsonValue | undefined, label: string): ConversationSettingsAuthority => {
    const record = requireRecord(value, label);
    const authorityType = readRequiredTrimmedString(record, 'type', `${label}.type`);
    if (authorityType !== 'conversation' && authorityType !== 'automation' && authorityType !== 'messaging_account') {
        throw new TypeError(`${label}.type is invalid`);
    }
    return {
        type: authorityType,
        entityId: readRequiredTrimmedString(record, 'entity_id', `${label}.entity_id`),
        entityLabel: readRequiredTrimmedString(record, 'entity_label', `${label}.entity_label`),
        readOnly: readRequiredBooleanValue(record['read_only'], `${label}.read_only`)
    };
};

export { decodeConversationSettingsAuthority };
export type { ConversationSettingsAuthority, ConversationSettingsAuthorityEligibility, ConversationSettingsAuthorityType };
