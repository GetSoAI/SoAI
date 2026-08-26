/* SoAI - Superseded chat turn detection [frontend/assets/ts/features/chat/chatstreamservice/controller/turnSupersession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatTurnAdmissionStreamIdentity } from '@features/chat/chatstreamservice/types.ts';

interface SupersedingStreamIdentityLookup {
    getStreamIdentity(conversationId: string): ChatTurnAdmissionStreamIdentity | null;
}

const isChatTurnSuperseded = (streamService: SupersedingStreamIdentityLookup, inputArguments: { conversationId: string; assistantTimestamp: number }): boolean => {
    const liveIdentity = streamService.getStreamIdentity(inputArguments.conversationId);
    return liveIdentity !== null && liveIdentity.assistantTimestamp > inputArguments.assistantTimestamp;
};

export { isChatTurnSuperseded };
export type { SupersedingStreamIdentityLookup };
