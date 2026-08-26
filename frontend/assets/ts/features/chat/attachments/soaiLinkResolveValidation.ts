/* SoAI - Chat SoAI link resolve response validation [frontend/assets/ts/features/chat/attachments/soaiLinkResolveValidation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SoaiLinkResolveResponse } from '@core/api/contracts/webuiChatOperationContracts.ts';
import { extractSoaiPathTokenTexts } from '@core/soailinks/codec.ts';
import type { SoaiPathStoragePart } from '@features/chat/attachments/soaiPathContentPart.ts';
import { cloneSoaiPathDraftRecordContentPart, mapSoaiPathResolveRecord, resolveSoaiPathDraftRecordToken, type SoaiPathDraftRecord } from '@features/chat/attachments/soaiPathDraftRecords.ts';

const requireMatchingResolveRecords = (response: SoaiLinkResolveResponse, rawText: string): SoaiPathDraftRecord[] => {
    const localTokens = extractSoaiPathTokenTexts(rawText);
    if (localTokens.length === 0) {
        throw new Error('SoAI link resolve validation requires local tokens');
    }
    if (response.tokenCount < 1 || response.tokenCount !== localTokens.length || response.records.length !== localTokens.length) {
        throw new Error('SoAI link resolve response did not return one canonical record per token');
    }
    const records = response.records.map(mapSoaiPathResolveRecord);
    for (let index = 0; index < localTokens.length; index += 1) {
        const localToken = localTokens[index];
        const record = records[index];
        if (localToken === undefined || record === undefined || resolveSoaiPathDraftRecordToken(record) !== localToken.token || record.occurrenceIndex !== index) {
            throw new Error('SoAI link resolve response token order is invalid');
        }
    }
    return records;
};

const requireMatchingResolveContentParts = (response: SoaiLinkResolveResponse, rawText: string): SoaiPathStoragePart[] => requireMatchingResolveRecords(response, rawText).map(cloneSoaiPathDraftRecordContentPart);

export { requireMatchingResolveContentParts, requireMatchingResolveRecords };
