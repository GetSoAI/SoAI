/* SoAI - Chat feature message info modal contracts [frontend/assets/ts/features/chat/message/messageinfomodal/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMessage, ToolActivityItem } from '@features/chat/ChatTypes.ts';
import type { CopyActionDependencies } from '@features/chat/message/messageCopyNotifications.ts';

interface MessageInfoEscapeDependencies {
    escapeHtml(value: string): string;
}

type MessageInfoModalDependencies = MessageInfoEscapeDependencies & CopyActionDependencies;

interface MessageInfoContentElements {
    contentElement: HTMLElement;
    copyButton: HTMLButtonElement;
}

interface MessageInfoSectionContent {
    html: string;
    copyText: string | null;
}

export type { ChatMessage, MessageInfoContentElements, MessageInfoEscapeDependencies, MessageInfoModalDependencies, MessageInfoSectionContent, ToolActivityItem };
