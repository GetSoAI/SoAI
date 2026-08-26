/* SoAI - Messaging modal persistence payload boundary [frontend/assets/ts/features/settings/messaging/modalPersistencePayload.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { MessagingAccount, MessagingAccountCreate, MessagingAccountUpdate, MessagingCredentials } from '@core/api/contracts/messagingAccountContracts.ts';
import { hasMessagingCredentialReplacement, type MessagingDraft } from '@features/settings/messaging/modalDraft.ts';

const buildCredentials = (draft: MessagingDraft): MessagingCredentials => {
    if (draft.platform === 'telegram') {
        return { platform: 'telegram', ...draft.credentials.telegram };
    }
    if (draft.platform === 'discord') {
        return { platform: 'discord', ...draft.credentials.discord };
    }
    return { platform: 'whatsapp', ...draft.credentials.whatsapp };
};

const buildMessagingPersistencePayload = (draft: MessagingDraft, account: MessagingAccount | null): MessagingAccountCreate | MessagingAccountUpdate => {
    const shared = {
        label: draft.label,
        modelSettings: draft.modelSettings,
        locale: draft.locale,
        plaintextSecretRepliesEnabled: draft.plaintextSecretRepliesEnabled,
        acceptMessagesFromAnyone: draft.acceptMessagesFromAnyone,
        replaceExistingCallback: draft.replaceExistingCallback,
        authorizedSenders: draft.authorizedSenders
    };
    if (draft.mode === 'create') {
        return {
            ...shared,
            credentials: buildCredentials(draft)
        };
    }
    if (!account) throw new Error('Messaging edit payload requires an account');
    return {
        ...shared,
        credentials: hasMessagingCredentialReplacement(draft) ? buildCredentials(draft) : null,
        enabled: account.lifecycleState !== 'disabled',
        expectedRevision: account.revision
    };
};

export { buildMessagingPersistencePayload };
