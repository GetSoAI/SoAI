/* SoAI - Chat preset library mutation terminal outcomes [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/chatPresetLibraryMutationDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError, isNetworkError, isRequestTimeoutError } from '@core/apiError.ts';
import type { ChatPresetSections, WebuiChatPresetRecord } from '@core/api/contracts/webuiChatPresetContractTypes.ts';
import type { ChatPageApi } from '@features/chat/public.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n, type TranslationKey } from '@core/i18n/index.ts';
import { cloneJsonObject } from '@core/primitives/clone.ts';

type ChatPresetApi = ChatPageApi['webui']['chat']['presets'];

type ChatPresetMutationRequest = Readonly<{ type: 'create'; name: string; sections: ChatPresetSections }> | Readonly<{ type: 'rename'; presetId: string; expectedRevision: number; name: string }> | Readonly<{ type: 'replace'; presetId: string; expectedRevision: number; name: string; sections: ChatPresetSections }> | Readonly<{ type: 'delete'; presetId: string; expectedRevision: number }>;

type ChatPresetMutationFailure = 'name_conflict' | 'revision_conflict' | 'revision_exhausted' | 'limit_reached' | 'corrupt_record' | 'not_found' | 'ambiguous' | 'failed';

type ChatPresetMutationResult = Readonly<{ status: 'committed'; record: WebuiChatPresetRecord | null }> | Readonly<{ status: ChatPresetMutationFailure; error: Error }>;
type ChatPresetResetResult = Readonly<{ status: 'committed'; deleted: number }> | Readonly<{ status: 'failed'; error: Error }>;

const cloneChatPresetSections = (sections: ChatPresetSections): ChatPresetSections => ({
    ...(sections.general ? { general: cloneJsonObject(sections.general) } : {}),
    ...(sections.appearance ? { appearance: cloneJsonObject(sections.appearance) } : {}),
    ...(sections.completion ? { completion: cloneJsonObject(sections.completion) } : {}),
    ...(sections.voice ? { voice: cloneJsonObject(sections.voice) } : {}),
    ...(sections.files ? { files: cloneJsonObject(sections.files) } : {}),
    ...(sections.knowledge ? { knowledge: cloneJsonObject(sections.knowledge) } : {}),
    ...(sections.tools ? { tools: cloneJsonObject(sections.tools) } : {})
});

const cloneChatPresetRecord = (record: WebuiChatPresetRecord): WebuiChatPresetRecord => ({ ...record, sections: cloneChatPresetSections(record.sections) });

const reconcileCommittedChatPresetRecord = (records: readonly WebuiChatPresetRecord[], committed: WebuiChatPresetRecord): readonly WebuiChatPresetRecord[] => {
    const index = records.findIndex((record) => record.id === committed.id);
    if (index < 0) return [cloneChatPresetRecord(committed), ...records];
    const previous = records[index];
    const reconciled = records.map((record) => (record.id === committed.id ? cloneChatPresetRecord(committed) : record));
    if (previous && committed.modifiedAtMs > previous.modifiedAtMs) return [cloneChatPresetRecord(committed), ...reconciled.filter((record) => record.id !== committed.id)];
    return reconciled;
};

const translateChatPresetMutationFailure = (status: ChatPresetMutationFailure): string => {
    if (status === 'name_conflict') return i18n.t('chat.configuration.presetLibrary.errors.name_conflict');
    if (status === 'revision_conflict') return i18n.t('chat.configuration.presetLibrary.errors.revision_conflict');
    if (status === 'revision_exhausted') return i18n.t('chat.configuration.presetLibrary.errors.revision_exhausted');
    if (status === 'limit_reached') return i18n.t('chat.configuration.presetLibrary.errors.limit_reached');
    if (status === 'corrupt_record') return i18n.t('chat.configuration.presetLibrary.errors.corrupt_record');
    if (status === 'not_found') return i18n.t('chat.configuration.presetLibrary.errors.not_found');
    if (status === 'ambiguous') return i18n.t('chat.configuration.presetLibrary.errors.ambiguous');
    return i18n.t('chat.configuration.presetLibrary.errors.failed');
};

const classifyMutationError = <Failure>(error: Failure): ChatPresetMutationResult => {
    const runtimeError = error instanceof Error ? error : new Error('Chat preset mutation failed.');
    if (isNetworkError(error) || isRequestTimeoutError(error)) return { status: 'ambiguous', error: runtimeError };
    if (!(error instanceof APIError)) return { status: 'failed', error: runtimeError };
    if (error.status === 404) return { status: 'not_found', error };
    if (error.code === 'chat_preset_name_conflict') return { status: 'name_conflict', error };
    if (error.code === 'chat_preset_revision_conflict') return { status: 'revision_conflict', error };
    if (error.code === 'chat_preset_revision_exhausted') return { status: 'revision_exhausted', error };
    if (error.code === 'chat_preset_limit_reached') return { status: 'limit_reached', error };
    if (error.code === 'chat_preset_corrupt_record') return { status: 'corrupt_record', error };
    return { status: 'failed', error };
};

const executeChatPresetMutation = async (api: ChatPresetApi, request: ChatPresetMutationRequest): Promise<ChatPresetMutationResult> => {
    try {
        if (request.type === 'create') {
            const record = await api.create({ name: request.name, sections: request.sections });
            return { status: 'committed', record };
        }
        if (request.type === 'rename') {
            const record = await api.rename(request.presetId, { expectedRevision: request.expectedRevision, name: request.name });
            return { status: 'committed', record };
        }
        if (request.type === 'replace') {
            const record = await api.replace(request.presetId, { expectedRevision: request.expectedRevision, name: request.name, sections: request.sections });
            return { status: 'committed', record };
        }
        await api.delete(request.presetId, request.expectedRevision);
        return { status: 'committed', record: null };
    } catch (error) {
        return classifyMutationError(ensureError(error));
    }
};

const executeChatPresetReset = async (api: ChatPresetApi): Promise<ChatPresetResetResult> => {
    try {
        return { status: 'committed', deleted: (await api.reset()).deleted };
    } catch (error) {
        const failure = ensureError(error);
        errorHandler.error('ChatPresetLibrary', 'Preset library reset failed', failure);
        return { status: 'failed', error: failure };
    }
};

const translateActionFailure = (messageKey: TranslationKey): string => {
    if (messageKey === 'chat.configuration.presetLibrary.resetFailed') return i18n.t('chat.configuration.presetLibrary.resetFailed');
    if (messageKey === 'chat.configuration.presetLibrary.applyFailed') return i18n.t('chat.configuration.presetLibrary.applyFailed');
    return i18n.t('chat.configuration.presetLibrary.errors.failed');
};

const reportChatPresetActionFailure = <Failure>(error: Failure, diagnostic: string, messageKey: TranslationKey, show: (message: string) => void): void => {
    errorHandler.error('ChatPresetLibrary', diagnostic, ensureError(error));
    show(translateActionFailure(messageKey));
};

export { cloneChatPresetRecord, cloneChatPresetSections, executeChatPresetMutation, executeChatPresetReset, reconcileCommittedChatPresetRecord, reportChatPresetActionFailure, translateChatPresetMutationFailure };
export type { ChatPresetMutationRequest, ChatPresetMutationResult };
