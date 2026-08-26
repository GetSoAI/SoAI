/* SoAI - Canonical chat soai_knowledge message segment parsing [frontend/assets/ts/features/chat/message/soaiKnowledgeMessageSegment.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';
import { normalizeSoaiKnowledgeContentPart } from '@features/chat/attachments/soaiKnowledgeContentPart.ts';
import type { SoaiKnowledgeSegment } from '@features/chat/message/messageSegments.ts';

const resolveSoaiKnowledgeSegment = (part: JsonObject, index: number): SoaiKnowledgeSegment => {
    const normalized = normalizeSoaiKnowledgeContentPart(part);
    if (normalized === null) {
        throw new Error(`Message content[${String(index)}] must be a canonical soai_knowledge part`);
    }
    return normalized;
};

export { resolveSoaiKnowledgeSegment };
