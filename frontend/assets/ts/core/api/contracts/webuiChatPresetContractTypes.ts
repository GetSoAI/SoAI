/* SoAI - WebUI chat preset wire contract types [frontend/assets/ts/core/api/contracts/webuiChatPresetContractTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';

type ChatPresetSectionId = 'general' | 'appearance' | 'completion' | 'voice' | 'files' | 'knowledge' | 'tools';

interface ChatPresetSections {
    general?: JsonObject;
    appearance?: JsonObject;
    completion?: JsonObject;
    voice?: JsonObject;
    files?: JsonObject;
    knowledge?: JsonObject;
    tools?: JsonObject;
}

interface WebuiChatPresetRecord {
    id: string;
    name: string;
    sections: ChatPresetSections;
    revision: number;
    createdAtMs: number;
    modifiedAtMs: number;
    omittedSettingsCount: number;
    applicable: boolean;
}

interface WebuiChatPresetListResponse {
    presets: WebuiChatPresetRecord[];
    structurallyInvalidCount: number;
}

interface WebuiChatPresetCreateRequest {
    name: string;
    sections: ChatPresetSections;
}

interface WebuiChatPresetRenameRequest {
    expectedRevision: number;
    name: string;
}

interface WebuiChatPresetReplaceRequest extends WebuiChatPresetCreateRequest {
    expectedRevision: number;
}

interface WebuiChatPresetResetResponse {
    deleted: number;
}

export type { ChatPresetSectionId, ChatPresetSections, WebuiChatPresetCreateRequest, WebuiChatPresetListResponse, WebuiChatPresetRecord, WebuiChatPresetRenameRequest, WebuiChatPresetReplaceRequest, WebuiChatPresetResetResponse };
