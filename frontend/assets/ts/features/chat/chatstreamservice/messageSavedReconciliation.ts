/* SoAI - Chat stream message-saved reconciliation results [frontend/assets/ts/features/chat/chatstreamservice/messageSavedReconciliation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatStreamStartAdmission } from '@features/chat/chatstreamservice/types.ts';

type ChatStreamMessageSavedReconciliationReason = 'inactive-no-stream-session' | 'active-stream' | 'terminalized-session' | 'suppressed-or-superseded-active-status' | 'stale-generation' | 'status-sync-timeout';

type CanonicalMessageLoadReason = Exclude<ChatStreamMessageSavedReconciliationReason, 'active-stream'>;
type SkippedCanonicalMessageLoadReason = Extract<ChatStreamMessageSavedReconciliationReason, 'active-stream'>;

type CanonicalMessageLoadReconciliation = {
    canonicalLoad: true;
    reason: CanonicalMessageLoadReason;
    startAdmission: ChatStreamStartAdmission;
};

type SkippedCanonicalMessageLoadReconciliation = {
    canonicalLoad: false;
    reason: SkippedCanonicalMessageLoadReason;
    startAdmission: ChatStreamStartAdmission;
};

type ChatStreamMessageSavedReconciliation = CanonicalMessageLoadReconciliation | SkippedCanonicalMessageLoadReconciliation;

const requireCanonicalMessageLoad = (reason: CanonicalMessageLoadReason = 'inactive-no-stream-session', startAdmission: ChatStreamStartAdmission = reason === 'inactive-no-stream-session' ? 'inactive' : 'unknown'): ChatStreamMessageSavedReconciliation => ({
    canonicalLoad: true,
    reason,
    startAdmission
});

const skipCanonicalMessageLoad = (reason: SkippedCanonicalMessageLoadReason, startAdmission: ChatStreamStartAdmission): ChatStreamMessageSavedReconciliation => ({
    canonicalLoad: false,
    reason,
    startAdmission
});

export { requireCanonicalMessageLoad, skipCanonicalMessageLoad };
export type { ChatStreamMessageSavedReconciliation, ChatStreamMessageSavedReconciliationReason };
