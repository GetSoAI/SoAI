/* SoAI - Chat SoAI path content preview payload parsing [frontend/assets/ts/features/chat/message/soaiPathContentPreviewPayload.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SoaiPathOpenResponse, SoaiPathPreviewResponse, SoaiPathTokenResponse } from '@core/api/contracts/webuiChatOperationContracts.ts';
import type { ContentPreviewSourceReference } from '@core/ui/modals/contentpreview/types.ts';
import { cloneSoaiPathStoragePart, type SoaiPathStoragePart } from '@features/chat/attachments/soaiPathContentPart.ts';
import { normalizeConversationVirtualPathValue } from '@features/chat/validation/soaiPathValues.ts';

const requireSoaiPathContentPart = (value: SoaiPathStoragePart): SoaiPathStoragePart => cloneSoaiPathStoragePart(value);

const requireSourceValue = (contentPart: SoaiPathStoragePart): string => {
    const canonicalValue = normalizeConversationVirtualPathValue(contentPart.sourceReference.value);
    if (canonicalValue === null) {
        throw new Error('SoAI path preview requires canonical source_reference.value');
    }
    return canonicalValue;
};

const requireRootFingerprint = (contentPart: SoaiPathStoragePart): string => {
    const value = contentPart.workspaceScope.rootFingerprint;
    if (!value.trim()) {
        throw new Error('SoAI path preview requires workspace_scope.root_fingerprint');
    }
    return value.trim();
};

const resolvePreviewType = (contentPart: SoaiPathStoragePart): string => contentPart.previewType;

const resolveContentType = (contentPart: SoaiPathStoragePart): string | null => contentPart.mimeType;

const resolveContentLength = (contentPart: SoaiPathStoragePart): number | null => contentPart.sizeBytes;

const buildSourceReference = (conversationId: string, contentPart: SoaiPathStoragePart): ContentPreviewSourceReference => {
    return {
        type: 'conversation_soai_path',
        conversationId,
        rootFingerprint: requireRootFingerprint(contentPart),
        value: requireSourceValue(contentPart)
    };
};

const parseOpenVirtualPath = (response: SoaiPathOpenResponse): string | null => (response.state === 'available' ? response.virtualPath : null);

const parseSoaiPathToken = (response: SoaiPathTokenResponse): string => {
    if (response.state !== 'available') {
        throw new Error('SoAI path token is unavailable');
    }
    return response.token;
};

const parseFolderEntriesText = (response: SoaiPathPreviewResponse): string => {
    if (response.state !== 'available' || response.entries === undefined) {
        return '';
    }
    const lines: string[] = [];
    for (const entry of response.entries) {
        lines.push(`${entry.entryType}\t${entry.name}`);
    }
    return lines.join('\n');
};

export { buildSourceReference, parseFolderEntriesText, parseOpenVirtualPath, parseSoaiPathToken, requireSoaiPathContentPart, resolveContentLength, resolveContentType, resolvePreviewType };
