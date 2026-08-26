/* SoAI - Unavailable attachment message segment parsing [frontend/assets/ts/features/chat/message/soaiUnavailableMessageSegment.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';
import { normalizeSoaiUnavailableFileContentPart, normalizeSoaiUnavailableKnowledgeContentPart } from '@features/chat/attachments/soaiUnavailableContentPart.ts';
import type { SoaiFileUnavailableSegment, SoaiKnowledgeUnavailableSegment } from '@features/chat/message/messageSegments.ts';

const resolveSoaiFileUnavailableSegment = (part: JsonObject, index: number): SoaiFileUnavailableSegment => {
    const normalized = normalizeSoaiUnavailableFileContentPart(part);
    if (normalized === null) throw new Error(`Message content[${String(index)}] must be a canonical soai_file_unavailable part`);
    return normalized;
};

const resolveSoaiKnowledgeUnavailableSegment = (part: JsonObject, index: number): SoaiKnowledgeUnavailableSegment => {
    const normalized = normalizeSoaiUnavailableKnowledgeContentPart(part);
    if (normalized === null) throw new Error(`Message content[${String(index)}] must be a canonical soai_knowledge_unavailable part`);
    return normalized;
};

export { resolveSoaiFileUnavailableSegment, resolveSoaiKnowledgeUnavailableSegment };
