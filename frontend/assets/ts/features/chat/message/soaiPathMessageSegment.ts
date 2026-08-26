/* SoAI - Canonical chat soai_path message segment parsing [frontend/assets/ts/features/chat/message/soaiPathMessageSegment.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';
import { normalizeSoaiPathContentPart } from '@features/chat/attachments/soaiPathContentPart.ts';
import type { SoaiPathSegment } from '@features/chat/message/messageSegments.ts';

const resolveSoaiPathSegment = (part: JsonObject, index: number): SoaiPathSegment => {
    const normalized = normalizeSoaiPathContentPart(part);
    if (normalized === null) {
        throw new Error(`Message content[${String(index)}] must be a canonical soai_path part`);
    }
    const segment: SoaiPathSegment = {
        type: 'soai_path',
        title: normalized.title,
        virtualPath: normalized.sourceReference.value,
        rootFingerprint: normalized.workspaceScope.rootFingerprint,
        entryType: normalized.entryType,
        contentPart: { ...normalized },
        previewType: normalized.previewType
    };
    if (normalized.mimeType !== null) {
        segment.mimeType = normalized.mimeType;
    }
    if (normalized.sizeBytes !== null) {
        segment.sizeBytes = normalized.sizeBytes;
    }
    return segment;
};

export { resolveSoaiPathSegment };
