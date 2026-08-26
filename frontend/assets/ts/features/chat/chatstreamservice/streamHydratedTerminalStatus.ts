/* SoAI - Hydrated chat stream terminal status resolution [frontend/assets/ts/features/chat/chatstreamservice/streamHydratedTerminalStatus.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { resolveHydratedAssistantTerminalState, type AssistantTerminalState } from '@features/chat/message/assistantTerminalState.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';

const resolveHydratedTerminalStatusFromMessage = (message: ChatMessage): AssistantTerminalState | null => {
    return resolveHydratedAssistantTerminalState(message);
};

const resolveHydratedTerminalStatus = (session: ChatStreamSession): AssistantTerminalState | null => {
    return resolveHydratedTerminalStatusFromMessage(session.assistantMessage);
};

export { resolveHydratedTerminalStatus, resolveHydratedTerminalStatusFromMessage };
