/* SoAI - Chat page actions [frontend/assets/ts/pages/chat/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isChatActionId, isMcpConversationActionId } from '@features/chat/public.ts';

export type ChatActionId = import('@features/chat/public.ts').ChatActionId;
type ChatHostedActionId = import('@features/chat/public.ts').ChatActionId | import('@features/chat/public.ts').McpConversationActionId;

const isChatHostedActionId = (value: string | undefined): value is ChatHostedActionId => isChatActionId(value) || isMcpConversationActionId(value);

export { isChatActionId, isChatHostedActionId };
export type { ChatHostedActionId };
