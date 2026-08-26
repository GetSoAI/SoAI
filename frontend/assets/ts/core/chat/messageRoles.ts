/* SoAI - Shared chat message roles [frontend/assets/ts/core/chat/messageRoles.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type MessageRole = 'system' | 'developer' | 'user' | 'assistant' | 'tool';

const CHAT_MESSAGE_ROLES: readonly MessageRole[] = ['system', 'developer', 'user', 'assistant', 'tool'];

const isMessageRole = (value: string): value is MessageRole => CHAT_MESSAGE_ROLES.some((role) => role === value);

export { CHAT_MESSAGE_ROLES, isMessageRole };
export type { MessageRole };
