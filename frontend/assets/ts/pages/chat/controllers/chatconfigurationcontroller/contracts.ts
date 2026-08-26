/* SoAI - Chat preset library state and configuration contracts [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatPresetSections, WebuiChatPresetRecord } from '@core/api/contracts/webuiChatPresetContractTypes.ts';
import type { ChatPresetSectionId } from '@features/chat/public.ts';

type ChatPresetEditorMode = 'create' | 'rename' | 'replace';

type ChatPresetSectionChoice = Readonly<{
    id: ChatPresetSectionId;
    eligible: boolean;
    hydrated: boolean;
    reason: string | null;
}>;

type ChatPresetEditorDraft = {
    mode: ChatPresetEditorMode;
    targetId: string | null;
    expectedRevision: number | null;
    name: string;
    originalName: string;
    selectedSections: Set<ChatPresetSectionId>;
    targetUnavailable: boolean;
    reviewRequired: boolean;
    nameConflict: boolean;
};

type ChatPresetLibraryViewState = Readonly<{
    phase: 'idle' | 'loading' | 'ready' | 'error';
    records: readonly WebuiChatPresetRecord[];
    searchQuery: string;
    stale: boolean;
    lastSuccessAtMs: number | null;
    structurallyInvalidCount: number;
    editor: ChatPresetEditorDraft | null;
    sectionChoices: readonly ChatPresetSectionChoice[];
    operationPending: boolean;
}>;

type ChatPresetSnapshotResult = Readonly<{ status: 'ready'; sections: ChatPresetSections; prunedValues: readonly string[] }> | Readonly<{ status: 'invalid'; message: string }>;

type ChatPresetApplyResult = Readonly<{
    changed: boolean;
    appliedSections: readonly ChatPresetSectionId[];
    skippedValues: readonly string[];
}>;

interface ChatPresetConfigurationPort {
    sectionChoices(): readonly ChatPresetSectionChoice[];
    snapshot(selectedSections: ReadonlySet<ChatPresetSectionId>): ChatPresetSnapshotResult;
    apply(record: WebuiChatPresetRecord, isSessionActive: () => boolean): Promise<ChatPresetApplyResult | null>;
    dirtySections(record: WebuiChatPresetRecord): readonly ChatPresetSectionId[];
}

const createChatPresetEditorDraft = (mode: ChatPresetEditorMode, record: WebuiChatPresetRecord | null, selectedSections: Set<ChatPresetSectionId>): ChatPresetEditorDraft => ({
    mode,
    targetId: record?.id ?? null,
    expectedRevision: record?.revision ?? null,
    name: record?.name ?? '',
    originalName: record?.name ?? '',
    selectedSections,
    targetUnavailable: false,
    reviewRequired: false,
    nameConflict: false
});

const createChatPresetRecordEditorDraft = (mode: Exclude<ChatPresetEditorMode, 'create'>, record: WebuiChatPresetRecord, sectionChoices: readonly ChatPresetSectionChoice[]): ChatPresetEditorDraft => {
    const selectedSections = new Set<ChatPresetSectionId>(Object.keys(record.sections).filter((sectionId): sectionId is ChatPresetSectionId => sectionChoices.some((choice) => choice.id === sectionId)));
    return createChatPresetEditorDraft(mode, record, selectedSections);
};

export { createChatPresetEditorDraft, createChatPresetRecordEditorDraft };
export type { ChatPresetApplyResult, ChatPresetConfigurationPort, ChatPresetEditorDraft, ChatPresetEditorMode, ChatPresetLibraryViewState, ChatPresetSectionChoice, ChatPresetSnapshotResult };
