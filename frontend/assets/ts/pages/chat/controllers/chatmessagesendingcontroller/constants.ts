/* SoAI - Chat message sending controller constants [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { minutesToMs, secondsToMs } from '@core/time/durations.ts';
import type { QueuedSendBlockReason, QueuedSendOutcome } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';

const CONVERSATION_EXPORT_REQUEST_TIMEOUT_MS = minutesToMs(15);
const CONVERSATION_EXPORT_TASK_POLL_INTERVAL_MS = secondsToMs(1);
const QUEUED_SEND_SENT: QueuedSendOutcome = { status: 'sent' };
const QUEUED_SEND_ABORTED: QueuedSendOutcome = { status: 'aborted' };

const blockQueuedSend = (reason: QueuedSendBlockReason): QueuedSendOutcome => ({ status: 'blocked', reason });

export { CONVERSATION_EXPORT_REQUEST_TIMEOUT_MS, CONVERSATION_EXPORT_TASK_POLL_INTERVAL_MS, QUEUED_SEND_ABORTED, QUEUED_SEND_SENT, blockQueuedSend };
