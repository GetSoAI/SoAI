/* SoAI - Chat feature stream run session sequence mismatch policy [frontend/assets/ts/features/chat/chatstreamservice/streamRunSessionSequenceMismatchPolicy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatStreamEventEnvelope } from '@core/realtime/eventcontracts/chatStreamEnvelope.ts';

type SequenceMismatchDecision =
    | {
          action: 'fail';
          message: string;
          errorCode: string | null;
          cancelReason: string | null;
      }
    | {
          action: 'pause';
      };

interface SequenceMismatchPolicy {
    decide: (inputArguments: { expectedSequence: number; receivedSequence: number; envelope: ChatStreamEventEnvelope }) => Promise<SequenceMismatchDecision> | SequenceMismatchDecision;
}

const createDefaultSequenceMismatchPolicy = (): SequenceMismatchPolicy => ({
    decide: ({ expectedSequence, receivedSequence }): SequenceMismatchDecision => ({
        action: 'fail',
        message: `Chat stream protocol error: expected sequence ${String(expectedSequence)} but received ${String(receivedSequence)}.`,
        errorCode: 'sequence_mismatch',
        cancelReason: `Client sequence mismatch: expected ${String(expectedSequence)} but received ${String(receivedSequence)}.`
    })
});

const resolveSequenceMismatchPolicy = (policy: SequenceMismatchPolicy | null | undefined): SequenceMismatchPolicy => {
    return policy ?? createDefaultSequenceMismatchPolicy();
};

export { resolveSequenceMismatchPolicy };
export type { SequenceMismatchDecision, SequenceMismatchPolicy };
