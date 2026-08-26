/* SoAI - Shared API conversation history timeout [frontend/assets/ts/core/api/conversationHistoryTimeout.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { minutesToMs } from '@core/time/durations.ts';

const CONVERSATION_HISTORY_REQUEST_TIMEOUT_MS = minutesToMs(5);

export { CONVERSATION_HISTORY_REQUEST_TIMEOUT_MS };
