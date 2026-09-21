/* SoAI - Chat feature inline activity name [frontend/assets/ts/features/chat/message/messageview/inlineActivityName.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { InlineRefreshActivitySegment } from '@features/chat/message/messageSegmentTypes.ts';
import { normalizeToolName } from '@features/chat/message/toolActivityPayloadFormatting.ts';

const resolveInlineActivityName = (segment: InlineRefreshActivitySegment): string => {
    switch (segment.type) {
        case 'inline_tool_activity':
            return normalizeToolName(segment.toolName);
        case 'inline_thinking_activity':
            return i18n.t('chat.thinking.label');
        case 'inline_loading_activity':
            return i18n.t('chat.loading.label');
        case 'inline_processing_activity':
            return i18n.t('chat.processing.label');
        case 'inline_wait_for_user_activity':
            return i18n.t('chat.waitForUser.label');
    }
};

export { resolveInlineActivityName };
