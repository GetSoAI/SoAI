/* SoAI - Chat feature ask user models [frontend/assets/ts/features/chat/askuser/askUserModels.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readRequiredJsonObjectArrayValue } from '@core/types/payloadRecordReaders.ts';
import { optionalTrimmedString, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { ConversationInteractionEntry, ConversationPendingInteractionResponse } from '@core/api/contracts/webuiChatOperationContracts.ts';
import { parsePendingInteractionEnvelope, parseConversationInputRecord } from '@features/chat/conversationinputs/envelopeParsing.ts';

type AskUserOption = {
    label: string;
    description: string;
};

type AskUserQuestion = {
    id: string;
    header: string | null;
    question: string;
    multiSelect: boolean;
    isSecret: boolean;
    options: AskUserOption[];
};

type AskUserPrompt = {
    taskId: string;
    notificationId: string | null;
    questions: AskUserQuestion[];
    createdAtMs: number;
};

type AskUserPendingResponse = {
    conversationId: string;
    prompt: AskUserPrompt | null;
};

function parseAskUserPendingResponse(response: ConversationPendingInteractionResponse): AskUserPendingResponse {
    const envelope = parsePendingInteractionEnvelope(response, 'ask_user');
    if (envelope.interaction === null) {
        return { conversationId: envelope.conversationId, prompt: null };
    }
    return { conversationId: envelope.conversationId, prompt: parseAskUserPrompt(envelope.interaction) };
}

function parseAskUserPrompt(interaction: ConversationInteractionEntry): AskUserPrompt {
    const prompt = parseConversationInputRecord(interaction, 'ask_user');
    const payload = prompt.payload;
    const questionsRaw = readRequiredJsonObjectArrayValue(payload['questions'], 'ask_user.questions');
    if (questionsRaw.length === 0) {
        throw new Error('ask_user.questions must be a non-empty array.');
    }
    const questions = questionsRaw.map(parseAskUserQuestion);
    return { taskId: prompt.taskId, notificationId: prompt.notificationId, createdAtMs: prompt.createdAtMs, questions };
}

function parseAskUserQuestion(record: JsonObject): AskUserQuestion {
    const id = readRequiredTrimmedString(record, 'id', 'id');
    const headerRaw = record['header'];
    const header = optionalTrimmedString(headerRaw);
    const question = readRequiredTrimmedString(record, 'question', 'question');
    const multiSelect = record['multiSelect'] === true;
    const isSecret = record['isSecret'] === true;
    const optionsRaw = readRequiredJsonObjectArrayValue(record['options'], 'ask_user.options');
    const options = optionsRaw.map(parseAskUserOption);
    return { id, header, question, multiSelect, isSecret, options };
}

function parseAskUserOption(record: JsonObject): AskUserOption {
    const label = readRequiredTrimmedString(record, 'label', 'label');
    const description = readRequiredTrimmedString(record, 'description', 'description');
    return { label, description };
}

export { parseAskUserPendingResponse };
export type { AskUserOption, AskUserPendingResponse, AskUserPrompt, AskUserQuestion };
