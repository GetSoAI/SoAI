/* SoAI - Localized presentation for chat stream failures [frontend/assets/ts/features/chat/chatstreamservice/streamErrorPresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { JsonRecord, JsonValue } from '@core/types/jsonValues.ts';
import { isString } from '@core/typeGuards.ts';
import { resolvePreviewContractReasonMessage } from '@features/chat/chatstreamservice/streamPreviewContractPresentation.ts';

type ChatStreamClientErrorCode = 'ws_disconnected' | 'stream_hydration_failed' | 'sequence_mismatch' | 'protocol_error' | 'client_error' | 'client_hook_failed';
type ChatStreamServerErrorCode = 'server_error' | 'service_unavailable' | 'empty_response' | 'model_output_contract_error' | 'model_stopped_error' | 'model_deleted_error' | 'tool_sequence_contract_violation' | 'preview_contract_violation' | 'forbidden_error' | 'not_found_error' | 'conflict_error' | 'accelerator_memory_exhausted' | 'system_memory_exhausted';

const isChatStreamClientErrorCode = (value: JsonValue): value is ChatStreamClientErrorCode => {
    if (!isString(value)) {
        return false;
    }
    switch (value) {
        case 'ws_disconnected':
        case 'stream_hydration_failed':
        case 'sequence_mismatch':
        case 'protocol_error':
        case 'client_error':
        case 'client_hook_failed':
            return true;
        default:
            return false;
    }
};

const resolveChatStreamClientErrorBaseMessage = (code: ChatStreamClientErrorCode): string => {
    switch (code) {
        case 'ws_disconnected':
            return i18n.t('chat.stream.errors.ws_disconnected');
        case 'stream_hydration_failed':
            return i18n.t('chat.stream.errors.stream_hydration_failed');
        case 'sequence_mismatch':
            return i18n.t('chat.stream.errors.sequence_mismatch');
        case 'protocol_error':
            return i18n.t('chat.stream.errors.protocol_error');
        case 'client_error':
            return i18n.t('chat.stream.errors.client_error');
        case 'client_hook_failed':
            return i18n.t('chat.stream.errors.client_hook_failed');
    }
};

const isChatStreamServerErrorCode = (value: JsonValue): value is ChatStreamServerErrorCode => {
    if (!isString(value)) {
        return false;
    }
    switch (value) {
        case 'server_error':
        case 'service_unavailable':
        case 'empty_response':
        case 'model_output_contract_error':
        case 'model_stopped_error':
        case 'model_deleted_error':
        case 'tool_sequence_contract_violation':
        case 'preview_contract_violation':
        case 'forbidden_error':
        case 'not_found_error':
        case 'conflict_error':
        case 'accelerator_memory_exhausted':
        case 'system_memory_exhausted':
            return true;
        default:
            return false;
    }
};

const resolveChatStreamServerErrorBaseMessage = (code: string): string => {
    switch (code) {
        case 'server_error':
            return i18n.t('chat.stream.errors.server_error');
        case 'service_unavailable':
            return i18n.t('chat.stream.errors.service_unavailable');
        case 'empty_response':
            return i18n.t('chat.stream.errors.empty_response');
        case 'model_output_contract_error':
            return i18n.t('chat.stream.errors.model_output_contract_error');
        case 'model_stopped_error':
            return i18n.t('chat.stream.errors.model_stopped_error');
        case 'model_deleted_error':
            return i18n.t('chat.stream.errors.model_deleted_error');
        case 'tool_sequence_contract_violation':
            return i18n.t('chat.stream.errors.tool_sequence_contract_violation');
        case 'preview_contract_violation':
            return i18n.t('chat.stream.errors.preview_contract_violation');
        case 'forbidden_error':
            return i18n.t('chat.stream.errors.forbidden_error');
        case 'not_found_error':
            return i18n.t('chat.stream.errors.not_found_error');
        case 'conflict_error':
            return i18n.t('chat.stream.errors.conflict_error');
        case 'accelerator_memory_exhausted':
            return i18n.t('chat.stream.errors.accelerator_memory_exhausted');
        case 'system_memory_exhausted':
            return i18n.t('chat.stream.errors.system_memory_exhausted');
        default:
            return i18n.t('chat.stream.errors.server_error');
    }
};

const resolveChatStreamServerErrorMessage = (_technicalMessage: string, code: string): string => {
    return resolveChatStreamServerErrorBaseMessage(code);
};

const buildChatStreamClientErrorPresentation = (inputArguments: { code: ChatStreamClientErrorCode; technicalMessage: string }): { lastError: JsonRecord; timelineMessage: string } => {
    const technicalMessage = inputArguments.technicalMessage.trim() ? inputArguments.technicalMessage.trim() : inputArguments.code;
    const timelineMessage = resolveChatStreamClientErrorBaseMessage(inputArguments.code);
    const userMessage = i18n.t('chat.stream.errors.withCode', { message: timelineMessage, code: inputArguments.code });
    return {
        lastError: {
            message: technicalMessage,
            code: inputArguments.code,
            userMessage: userMessage
        },
        timelineMessage
    };
};

const buildChatStreamServerErrorPresentation = (inputArguments: { code: string; technicalMessage: string; referenceId: string; previewContract?: JsonValue }): { lastError: JsonRecord; timelineMessage: string } => {
    const technicalMessage = inputArguments.technicalMessage.trim() ? inputArguments.technicalMessage.trim() : inputArguments.code;
    const baseMessage = resolveChatStreamServerErrorBaseMessage(inputArguments.code);
    const previewReason = inputArguments.code === 'preview_contract_violation' && inputArguments.previewContract !== undefined ? resolvePreviewContractReasonMessage(inputArguments.previewContract) : null;
    const actionableMessage = previewReason === null ? baseMessage : `${baseMessage} ${previewReason}`;
    const timelineMessage = i18n.t('chat.stream.errors.withReference', { message: actionableMessage, code: inputArguments.code, referenceId: inputArguments.referenceId });
    return {
        lastError: {
            message: technicalMessage,
            code: inputArguments.code,
            referenceId: inputArguments.referenceId,
            userMessage: timelineMessage,
            ...(inputArguments.previewContract !== undefined ? { 'preview_contract': inputArguments.previewContract } : {})
        },
        timelineMessage
    };
};

export { buildChatStreamClientErrorPresentation, buildChatStreamServerErrorPresentation, isChatStreamClientErrorCode, isChatStreamServerErrorCode, resolveChatStreamClientErrorBaseMessage, resolveChatStreamServerErrorBaseMessage, resolveChatStreamServerErrorMessage };
export type { ChatStreamClientErrorCode, ChatStreamServerErrorCode };
