/* SoAI - Voice call assistant speech segmentation [frontend/assets/ts/pages/chat/controllers/voicecall/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import type { MessageSegment } from '@features/chat/public.ts';

const resolveTextOnly = (segments: MessageSegment[]): string => {
    const fragments: string[] = [];
    for (const segment of segments) {
        if (segment.type !== 'text') {
            continue;
        }
        const value = segment.value;
        if (isString(value) && value.trim()) {
            fragments.push(value.trim());
        }
    }
    return fragments.join('\n').trim();
};

export { resolveTextOnly };
