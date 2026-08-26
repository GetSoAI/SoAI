/* SoAI - Chat feature secret prompt models [frontend/assets/ts/features/chat/secretprompt/secretPromptModels.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationPendingInteractionResponse } from '@core/api/contracts/webuiChatOperationContracts.ts';
import { isBoolean } from '@core/typeGuards.ts';
import { readRequiredJsonObjectArrayValue, requireRecord } from '@core/types/payloadRecordReaders.ts';
import { optionalTrimmedString, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';
import { parsePendingInteractionEnvelope, parseConversationInputRecord } from '@features/chat/conversationinputs/envelopeParsing.ts';

type SecretPromptScope = { scopeType: 'origin'; origin: string };

type SecretPromptFieldId = 'username' | 'password';

type SecretPromptField = { id: SecretPromptFieldId; type: 'text' | 'password'; optional: boolean };

type SecretPrompt = {
    taskId: string;
    notificationId: string | null;
    title: string;
    message: string;
    fields: readonly SecretPromptField[];
    scope: SecretPromptScope;
    allowSaveToVault: boolean;
    saveLabelDefault: string | null;
    createdAtMs: number;
};

type SecretPromptPendingResponse = { conversationId: string; prompt: SecretPrompt | null };

const SECRET_PROMPT_FIELD_IDS: ReadonlySet<string> = new Set(['username', 'password']);

const isSecretPromptFieldId = (value: string): value is SecretPromptFieldId => SECRET_PROMPT_FIELD_IDS.has(value);

const parseSecretPromptPendingResponse = (response: ConversationPendingInteractionResponse): SecretPromptPendingResponse => {
    const envelope = parsePendingInteractionEnvelope(response, 'secret_prompt');
    if (envelope.interaction === null) {
        return { conversationId: envelope.conversationId, prompt: null };
    }
    const prompt = parseConversationInputRecord(envelope.interaction, 'secret_prompt');
    const payload = prompt.payload;
    const title = readRequiredTrimmedString(payload, 'title', 'title');
    const message = readRequiredTrimmedString(payload, 'message', 'message');

    const fieldsRaw = readRequiredJsonObjectArrayValue(payload['fields'], 'secret_prompt.fields');
    if (fieldsRaw.length === 0) {
        throw new Error('secret_prompt.fields must be a non-empty array.');
    }
    const fields: SecretPromptField[] = [];
    for (const entryRecord of fieldsRaw) {
        const id = readRequiredTrimmedString(entryRecord, 'id', 'id');
        const type = readRequiredTrimmedString(entryRecord, 'type', 'type');
        const optionalRaw = entryRecord['optional'];
        const optional = isBoolean(optionalRaw) ? optionalRaw : false;
        if (!isSecretPromptFieldId(id)) {
            throw new Error(`secret_prompt.field.id is invalid: ${id}`);
        }
        if (type !== 'text' && type !== 'password') {
            throw new Error(`secret_prompt.field.type is invalid: ${type}`);
        }
        fields.push({ id, type, optional });
    }

    const scopeRecord = requireRecord(payload['scope'], 'secret_prompt.scope');
    const scopeType = readRequiredTrimmedString(scopeRecord, 'scope_type', 'scope_type');
    if (scopeType !== 'origin') {
        throw new Error(`secret_prompt.scope_type is invalid: ${scopeType}`);
    }
    const origin = readRequiredTrimmedString(scopeRecord, 'origin', 'origin');
    const scope: SecretPromptScope = { scopeType: 'origin', origin };

    const allowSaveRaw = payload['allow_save_to_vault'];
    const allowSaveToVault = isBoolean(allowSaveRaw) ? allowSaveRaw : false;
    const saveLabelDefaultRaw = payload['save_label_default'];
    const saveLabelDefault = optionalTrimmedString(saveLabelDefaultRaw);
    return {
        conversationId: envelope.conversationId,
        prompt: { taskId: prompt.taskId, notificationId: prompt.notificationId, title, message, fields, scope, allowSaveToVault, saveLabelDefault, createdAtMs: prompt.createdAtMs }
    };
};

export { parseSecretPromptPendingResponse };
export type { SecretPrompt, SecretPromptField, SecretPromptScope, SecretPromptFieldId };
