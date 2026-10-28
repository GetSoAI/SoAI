/* SoAI - Conversation input lifecycle classification [frontend/assets/ts/core/chat/conversationInputLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CONVERSATION_INPUT_TERMINAL_STATES, type ConversationInputLifecycleState, type ConversationInputTerminalState } from '@core/chat/protocols.ts';

const isConversationInputTerminalState = (state: ConversationInputLifecycleState): state is ConversationInputTerminalState => CONVERSATION_INPUT_TERMINAL_STATES.some((terminalState) => terminalState === state);

export { isConversationInputTerminalState };
