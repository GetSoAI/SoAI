/* SoAI - Chat feature message actions copy [frontend/assets/ts/features/chat/message/messageActionsCopy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { stripPreviewReferenceTokensForClipboard } from '@features/chat/message/enhancers/inlineMultimediaPreviewContract.ts';
import { copyTextWithNotification, type CopyActionDependencies } from '@features/chat/message/messageCopyNotifications.ts';
import { resolveImageSegment, resolveSegmentText } from '@features/chat/message/messageview/mappers.ts';
import type { MessageSegment } from '@features/chat/message/messageSegments.ts';

interface ChatMessageCopyDependencies extends CopyActionDependencies {
    resolveMessageContentSegments: (message: ChatMessage) => MessageSegment[];
}

const buildCopyableMessageText = (dependencies: ChatMessageCopyDependencies, message: ChatMessage): string => {
    const segments = dependencies.resolveMessageContentSegments(message);
    const parts: string[] = [];
    for (const segment of segments) {
        if (!segment) {
            continue;
        }
        if (segment.type === 'text') {
            const textValue = resolveSegmentText(segment).value;
            if (textValue) {
                parts.push(stripPreviewReferenceTokensForClipboard(textValue));
            }
            continue;
        }
        if (message.role === 'user') {
            continue;
        }
        if (segment.type !== 'image') {
            continue;
        }
        const resolvedImage = resolveImageSegment(segment);
        if (resolvedImage === null) {
            continue;
        }
        parts.push(`![${resolvedImage.label}](${resolvedImage.src})`);
    }
    return parts.join('\n\n').trim();
};

const copyMessageText = async (dependencies: ChatMessageCopyDependencies, message: ChatMessage): Promise<void> => {
    const text = buildCopyableMessageText(dependencies, message);
    await copyTextWithNotification(dependencies, 'chat:copyMessageText', text, i18n.t('chat.message.copied'));
};

const copyTimestamp = async (dependencies: ChatMessageCopyDependencies, timestamp: string): Promise<void> => {
    await copyTextWithNotification(dependencies, 'chat:copyTimestamp', timestamp, i18n.t('chat.message.timestampCopied'));
};

export { copyMessageText, copyTimestamp };
export type { ChatMessageCopyDependencies };
