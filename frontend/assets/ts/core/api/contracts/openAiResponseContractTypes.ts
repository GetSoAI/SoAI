/* SoAI - Frontend OpenAI response contract types [frontend/assets/ts/core/api/contracts/openAiResponseContractTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';

interface OpenAiUsage {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
    promptTokensDetails: JsonObject | null;
    completionTokensDetails: JsonObject | null;
}

interface OpenAiChatMessage {
    role: 'assistant';
    content: string | null;
    refusal: string | null;
    toolCalls: JsonObject[];
    annotations: JsonObject[];
    audio: JsonObject | null;
}

interface OpenAiChatCompletionChoice {
    index: number;
    message: OpenAiChatMessage;
    finishReason: string | null;
    logprobs: JsonObject | null;
}

interface OpenAiChatCompletionResponse {
    id: string;
    object: 'chat.completion';
    created: number;
    model: string;
    choices: OpenAiChatCompletionChoice[];
    usage: OpenAiUsage | null;
    systemFingerprint: string | null;
    serviceTier: string | null;
}

interface OpenAiCompletionChoice {
    text: string;
    index: number;
    logprobs: JsonObject | null;
    finishReason: string | null;
}

interface OpenAiCompletionResponse {
    id: string;
    object: 'text_completion';
    created: number;
    model: string;
    choices: OpenAiCompletionChoice[];
    usage: OpenAiUsage | null;
    systemFingerprint: string | null;
}

interface OpenAiEmbedding {
    object: 'embedding';
    embedding: number[];
    index: number;
}

interface OpenAiEmbeddingUsage {
    promptTokens: number;
    totalTokens: number;
}

interface OpenAiEmbeddingResponse {
    object: 'list';
    data: OpenAiEmbedding[];
    model: string;
    usage: OpenAiEmbeddingUsage;
}

interface OpenAiImageData {
    url: string | null;
    b64Json: string | null;
    revisedPrompt: string | null;
}

interface OpenAiImageTokenDetails {
    textTokens?: number | undefined;
    imageTokens?: number | undefined;
}

interface OpenAiImageUsage {
    inputTokens?: number | undefined;
    outputTokens?: number | undefined;
    totalTokens?: number | undefined;
    inputTokensDetails?: OpenAiImageTokenDetails | undefined;
}

interface OpenAiImageResponse {
    created: number;
    data: OpenAiImageData[];
    usage: OpenAiImageUsage | null;
}

interface OpenAiTranscriptionResponse {
    text: string;
    language: string | null;
    duration: number | null;
    words: JsonObject[];
    segments: JsonObject[];
    usage: JsonObject | null;
}

export type { OpenAiChatCompletionChoice, OpenAiChatCompletionResponse, OpenAiChatMessage, OpenAiCompletionChoice, OpenAiCompletionResponse, OpenAiEmbedding, OpenAiEmbeddingResponse, OpenAiEmbeddingUsage, OpenAiImageData, OpenAiImageResponse, OpenAiImageTokenDetails, OpenAiImageUsage, OpenAiTranscriptionResponse, OpenAiUsage };
