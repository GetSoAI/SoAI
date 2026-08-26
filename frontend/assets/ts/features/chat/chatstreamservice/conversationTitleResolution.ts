/* SoAI - Chat stream conversation title resolution [frontend/assets/ts/features/chat/chatstreamservice/conversationTitleResolution.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';

type ConversationTitleResolver = (conversationId: string) => string | null;

const resolveNotificationTitle = (value: string | null): string | null => {
    const title = toTrimmedString(value);
    if (!title) {
        return null;
    }
    return title.replace(/["'`\u2018\u2019\u201c\u201d]/g, '').trim() ? title : null;
};

class ChatStreamConversationTitleResolution {
    #resolver: ConversationTitleResolver | null = null;

    setResolver(resolver: ConversationTitleResolver): () => void {
        this.#resolver = resolver;
        return () => {
            if (this.#resolver === resolver) {
                this.#resolver = null;
            }
        };
    }

    resolve(session: ChatStreamSession): string | null {
        const sessionTitle = resolveNotificationTitle(session.conversationTitle);
        if (sessionTitle) {
            return sessionTitle;
        }
        return resolveNotificationTitle(this.#resolver?.(session.conversationId) ?? null);
    }

    clear(): void {
        this.#resolver = null;
    }
}

export { ChatStreamConversationTitleResolution };
export type { ConversationTitleResolver };
