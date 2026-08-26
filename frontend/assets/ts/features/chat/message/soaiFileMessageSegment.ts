/* SoAI - Canonical chat soai_file message segment parsing [frontend/assets/ts/features/chat/message/soaiFileMessageSegment.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';
import { normalizeSoaiFileContentPart } from '@features/chat/attachments/soaiFileContentPart.ts';
import type { SoaiFileSegment } from '@features/chat/message/messageSegments.ts';

const resolveSoaiFileSegment = (part: JsonObject, index: number): SoaiFileSegment => {
    const normalized = normalizeSoaiFileContentPart(part);
    if (normalized === null) {
        throw new Error(`Message content[${String(index)}] must be a canonical soai_file part`);
    }
    return normalized;
};

export { resolveSoaiFileSegment };
