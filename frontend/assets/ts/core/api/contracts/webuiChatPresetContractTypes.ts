/* SoAI - WebUI chat preset wire contract types [frontend/assets/ts/core/api/contracts/webuiChatPresetContractTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';

type ChatPresetSectionId = 'general' | 'appearance' | 'completion' | 'voice' | 'files' | 'knowledge' | 'skills' | 'tools';

type ChatPresetSections = {
    general?: JsonObject;
    appearance?: JsonObject;
    completion?: JsonObject;
    voice?: JsonObject;
    files?: JsonObject;
    knowledge?: JsonObject;
    skills?: JsonObject;
    tools?: JsonObject;
};

type WebuiChatPresetRecord = {
    id: string;
    name: string;
    sections: ChatPresetSections;
    revision: number;
    createdAtMs: number;
    modifiedAtMs: number;
    omittedSettingsCount: number;
    applicable: boolean;
};

type WebuiChatPresetListResponse = {
    presets: WebuiChatPresetRecord[];
    structurallyInvalidCount: number;
};

type WebuiChatPresetCreateRequest = {
    name: string;
    sections: ChatPresetSections;
};

type WebuiChatPresetRenameRequest = {
    expectedRevision: number;
    name: string;
};

interface WebuiChatPresetReplaceRequest extends WebuiChatPresetCreateRequest {
    expectedRevision: number;
}

type WebuiChatPresetResetResponse = {
    deleted: number;
};

export type { ChatPresetSectionId, ChatPresetSections, WebuiChatPresetCreateRequest, WebuiChatPresetListResponse, WebuiChatPresetRecord, WebuiChatPresetRenameRequest, WebuiChatPresetReplaceRequest, WebuiChatPresetResetResponse };
