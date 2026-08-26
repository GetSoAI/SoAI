/* SoAI - Chat page message target resolution controller [frontend/assets/ts/pages/chat/controllers/page/events/messageTargetResolutionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import { normalizeMessageDomId } from '@features/chat/public.ts';
import type { ChatRootEventsHost } from '@pages/chat/controllers/page/events/contracts.ts';

const resolveNormalizedMessageIdForTarget = (host: ChatRootEventsHost, target: Element): string | null => {
    const messageId = host.messages.resolveMessageIdForTarget(target);
    if (!isString(messageId)) {
        return null;
    }
    return normalizeMessageDomId(messageId);
};

export { resolveNormalizedMessageIdForTarget };
