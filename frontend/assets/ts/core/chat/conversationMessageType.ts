/* SoAI - Canonical conversation message type contract [frontend/assets/ts/core/chat/conversationMessageType.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type ConversationMessageType = 'chat' | 'control';

const CONVERSATION_MESSAGE_TYPES: readonly ConversationMessageType[] = ['chat', 'control'];

const isConversationMessageType = <T>(value: T): value is T & ConversationMessageType => value === 'chat' || value === 'control';

export { CONVERSATION_MESSAGE_TYPES, isConversationMessageType };
export type { ConversationMessageType };
