/* SoAI - Localized presentation for chat stream failures [frontend/assets/ts/features/chat/chatstreamservice/streamErrorPresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { resolveOperationCauseMessage } from '@core/errors/operationCausePresentation.ts';
import { isSkillErrorCode, resolveSkillErrorMessage, type SkillErrorCode } from '@core/skills/errorPresentation.ts';
import type { ChatStreamErrorsTranslationKey } from '@core/i18n/translationkeys/chat/stream__errors.generated.ts';
import { isJsonObject, type JsonRecord, type JsonValue } from '@core/types/jsonValues.ts';
import { isString } from '@core/typeGuards.ts';
import { resolveContextBudgetErrorMessage, resolveContextUsageMessage } from '@features/chat/chatErrorPresentation.ts';
import { resolvePreviewContractReasonMessage } from '@features/chat/chatstreamservice/streamPreviewContractPresentation.ts';

type ChatStreamClientErrorCode = 'ws_disconnected' | 'stream_hydration_failed' | 'sequence_mismatch' | 'protocol_error' | 'client_error' | 'client_hook_failed';
type ChatStreamServerErrorCode = SkillErrorCode | 'server_error' | 'service_unavailable' | 'empty_response' | 'model_output_contract_error' | 'model_stopped_error' | 'model_deleted_error' | 'tool_sequence_contract_violation' | 'preview_contract_violation' | 'forbidden_error' | 'not_found_error' | 'conflict_error' | 'accelerator_memory_exhausted' | 'system_memory_exhausted';

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
    if (isSkillErrorCode(value)) return true;
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
    const skillMessage = resolveSkillErrorMessage(code);
    if (skillMessage) return skillMessage;
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
        case 'invalid_request_error':
            return i18n.t('chat.stream.errors.invalid_request_error');
        case 'authentication_error':
            return i18n.t('chat.stream.errors.authentication_error');
        case 'payment_required_error':
            return i18n.t('chat.stream.errors.payment_required_error');
        case 'rate_limit_error':
        case 'overloaded_error':
            return i18n.t('chat.stream.errors.rate_limit_error');
        case 'timeout_error':
            return i18n.t('chat.stream.errors.timeout_error');
        case 'plugin_unavailable_error':
            return i18n.t('chat.stream.errors.service_unavailable');
        case 'context_budget_unavailable':
            return i18n.t('chat.stream.errors.context_budget_unavailable');
        default:
            return i18n.t('chat.stream.errors.server_error');
    }
};

const resolveChatStreamServerErrorMessage = (technicalMessage: string, code: string, details?: JsonValue, parameterName?: string, trustedSummary: boolean = false): string => {
    const causeMessage = resolveSkillErrorMessage(code, { details: details ?? null }) ?? resolveOperationCauseMessage(code, { payload: { details: details ?? null } });
    if (causeMessage) return causeMessage;
    const category = isJsonObject(details) ? details['upstream_failure_type'] : null;
    let message: string;
    switch (category) {
        case 'billing':
            message = resolveChatStreamServerErrorBaseMessage('payment_required_error');
            break;
        case 'authentication':
            message = resolveChatStreamServerErrorBaseMessage('authentication_error');
            break;
        case 'permission':
            message = i18n.t('chat.stream.errors.providerPermission');
            break;
        case 'invalid_parameter':
            message = parameterName ? i18n.t('chat.stream.errors.providerParameter', { 'param': parameterName }) : resolveChatStreamServerErrorBaseMessage('invalid_request_error');
            break;
        case 'invalid_media':
            switch (isJsonObject(details) ? details['upstream_media_reason'] : null) {
                case 'format':
                    message = i18n.t('chat.stream.errors.providerMediaFormat');
                    break;
                case 'size':
                    message = i18n.t('chat.stream.errors.providerMediaSize');
                    break;
                case 'decoding':
                    message = i18n.t('chat.stream.errors.providerMediaDecoding');
                    break;
                case 'retrieval':
                    message = i18n.t('chat.stream.errors.providerMediaRetrieval');
                    break;
                default:
                    message = i18n.t('chat.stream.errors.providerMedia');
            }
            break;
        case 'context_length':
            message = resolveContextUsageMessage(details);
            break;
        case 'content_policy':
            message = i18n.t('chat.stream.errors.providerContentPolicy');
            break;
        case 'unsupported_vision_request':
            message = i18n.t('chat.stream.errors.providerVision');
            break;
        case 'unsupported_audio_request':
            message = i18n.t('chat.stream.errors.providerAudio');
            break;
        case 'model_unavailable':
            message = i18n.t('chat.stream.errors.providerModelUnavailable');
            break;
        case 'provider_outage':
            message = i18n.t('chat.stream.errors.providerUnavailable');
            break;
        case 'rate_limit':
            message = resolveChatStreamServerErrorBaseMessage('rate_limit_error');
            break;
        case 'timeout':
            message = resolveChatStreamServerErrorBaseMessage('timeout_error');
            break;
        case 'invalid_request':
            message = resolveChatStreamServerErrorBaseMessage('invalid_request_error');
            break;
        default:
            message = resolveContextBudgetErrorMessage(code, details) ?? (trustedSummary && technicalMessage.trim() ? technicalMessage.trim() : resolveChatStreamServerErrorBaseMessage(code));
    }
    const retryAfter = isJsonObject(details) ? details['retry_after'] : null;
    return isString(retryAfter) && /^\d{1,16}$/.test(retryAfter) ? `${message} ${i18n.t('chat.stream.errors.providerRetryAfter', { seconds: retryAfter })}` : message;
};

const resolveProviderExplanationText = (explanation: string | null | undefined): string | null => {
    const trimmed = explanation?.trim();
    return trimmed ? i18n.t('chat.stream.errors.providerExplanation', { explanation: trimmed }) : null;
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

const buildChatStreamServerErrorPresentation = (inputArguments: { code: string; technicalMessage: string; referenceId: string; previewContract?: JsonValue; explanation?: string | undefined; parameterName?: string | undefined; details?: JsonValue | undefined; trustedSummary?: boolean }): { lastError: JsonRecord; timelineMessage: string } => {
    const technicalMessage = inputArguments.technicalMessage.trim() ? inputArguments.technicalMessage.trim() : inputArguments.code;
    const baseMessage = resolveChatStreamServerErrorMessage(technicalMessage, inputArguments.code, inputArguments.details, inputArguments.parameterName, inputArguments.trustedSummary);
    const previewReason = inputArguments.code === 'preview_contract_violation' && inputArguments.previewContract !== undefined ? resolvePreviewContractReasonMessage(inputArguments.previewContract) : null;
    const actionableMessage = previewReason === null ? baseMessage : `${baseMessage} ${previewReason}`;
    const timelineMessage = i18n.t('chat.stream.errors.withReference', { message: actionableMessage, code: inputArguments.code, referenceId: inputArguments.referenceId });
    const explanation = resolveProviderExplanationText(inputArguments.explanation);
    return {
        lastError: {
            message: technicalMessage,
            code: inputArguments.code,
            referenceId: inputArguments.referenceId,
            userMessage: explanation ? `${timelineMessage}\n${explanation}` : timelineMessage,
            ...(inputArguments.explanation !== undefined ? { explanation: inputArguments.explanation } : {}),
            ...(inputArguments.parameterName !== undefined ? { 'param': inputArguments.parameterName } : {}),
            ...(inputArguments.details !== undefined ? { details: inputArguments.details } : {}),
            ...(inputArguments.previewContract !== undefined ? { 'preview_contract': inputArguments.previewContract } : {})
        },
        timelineMessage
    };
};

const buildChatStreamErrorTranslations = (): Record<ChatStreamErrorsTranslationKey, string> => {
    return {
        'chat.stream.errors.client_error': i18n.t('chat.stream.errors.client_error'),
        'chat.stream.errors.client_hook_failed': i18n.t('chat.stream.errors.client_hook_failed'),
        'chat.stream.errors.accelerator_memory_exhausted': i18n.t('chat.stream.errors.accelerator_memory_exhausted'),
        'chat.stream.errors.conflict_error': i18n.t('chat.stream.errors.conflict_error'),
        'chat.stream.errors.empty_response': i18n.t('chat.stream.errors.empty_response'),
        'chat.stream.errors.forbidden_error': i18n.t('chat.stream.errors.forbidden_error'),
        'chat.stream.errors.model_deleted_error': i18n.t('chat.stream.errors.model_deleted_error'),
        'chat.stream.errors.model_output_contract_error': i18n.t('chat.stream.errors.model_output_contract_error'),
        'chat.stream.errors.model_stopped_error': i18n.t('chat.stream.errors.model_stopped_error'),
        'chat.stream.errors.not_found_error': i18n.t('chat.stream.errors.not_found_error'),
        'chat.stream.errors.preview_contract_violation': i18n.t('chat.stream.errors.preview_contract_violation'),
        'chat.stream.errors.preview_contract_reason_invalid_absolute_path_reference': i18n.t('chat.stream.errors.preview_contract_reason_invalid_absolute_path_reference'),
        'chat.stream.errors.preview_contract_reason_invalid_remote_url': i18n.t('chat.stream.errors.preview_contract_reason_invalid_remote_url'),
        'chat.stream.errors.preview_contract_reason_invalid_virtual_path_reference': i18n.t('chat.stream.errors.preview_contract_reason_invalid_virtual_path_reference'),
        'chat.stream.errors.preview_contract_reason_absolute_path_preview_scope_unavailable': i18n.t('chat.stream.errors.preview_contract_reason_absolute_path_preview_scope_unavailable'),
        'chat.stream.errors.preview_contract_reason_missing_preview_reference': i18n.t('chat.stream.errors.preview_contract_reason_missing_preview_reference'),
        'chat.stream.errors.preview_contract_reason_noncanonical_reference_syntax': i18n.t('chat.stream.errors.preview_contract_reason_noncanonical_reference_syntax'),
        'chat.stream.errors.protocol_error': i18n.t('chat.stream.errors.protocol_error'),
        'chat.stream.errors.sequence_mismatch': i18n.t('chat.stream.errors.sequence_mismatch'),
        'chat.stream.errors.server_error': i18n.t('chat.stream.errors.server_error'),
        'chat.stream.errors.system_memory_exhausted': i18n.t('chat.stream.errors.system_memory_exhausted'),
        'chat.stream.errors.service_unavailable': i18n.t('chat.stream.errors.service_unavailable'),
        'chat.stream.errors.stream_hydration_failed': i18n.t('chat.stream.errors.stream_hydration_failed'),
        'chat.stream.errors.tool_sequence_contract_violation': i18n.t('chat.stream.errors.tool_sequence_contract_violation'),
        'chat.stream.errors.invalid_request_error': i18n.t('chat.stream.errors.invalid_request_error'),
        'chat.stream.errors.authentication_error': i18n.t('chat.stream.errors.authentication_error'),
        'chat.stream.errors.payment_required_error': i18n.t('chat.stream.errors.payment_required_error'),
        'chat.stream.errors.rate_limit_error': i18n.t('chat.stream.errors.rate_limit_error'),
        'chat.stream.errors.timeout_error': i18n.t('chat.stream.errors.timeout_error'),
        'chat.stream.errors.providerExplanation': i18n.t('chat.stream.errors.providerExplanation', { explanation: '{explanation}' }),
        'chat.stream.errors.withCode': i18n.t('chat.stream.errors.withCode', { message: '{message}', code: '{code}' }),
        'chat.stream.errors.withReference': i18n.t('chat.stream.errors.withReference', { message: '{message}', code: '{code}', referenceId: '{referenceId}' }),
        'chat.stream.errors.ws_disconnected': i18n.t('chat.stream.errors.ws_disconnected'),
        'chat.stream.errors.providerPermission': i18n.t('chat.stream.errors.providerPermission'),
        'chat.stream.errors.providerParameter': i18n.t('chat.stream.errors.providerParameter', { 'param': '{param}' }),
        'chat.stream.errors.providerMedia': i18n.t('chat.stream.errors.providerMedia'),
        'chat.stream.errors.providerContext': i18n.t('chat.stream.errors.providerContext'),
        'chat.stream.errors.providerContentPolicy': i18n.t('chat.stream.errors.providerContentPolicy'),
        'chat.stream.errors.providerVision': i18n.t('chat.stream.errors.providerVision'),
        'chat.stream.errors.providerAudio': i18n.t('chat.stream.errors.providerAudio'),
        'chat.stream.errors.providerModelUnavailable': i18n.t('chat.stream.errors.providerModelUnavailable'),
        'chat.stream.errors.providerUnavailable': i18n.t('chat.stream.errors.providerUnavailable'),
        'chat.stream.errors.providerRetryAfter': i18n.t('chat.stream.errors.providerRetryAfter', { seconds: '{seconds}' }),
        'chat.stream.errors.providerMediaFormat': i18n.t('chat.stream.errors.providerMediaFormat'),
        'chat.stream.errors.providerMediaSize': i18n.t('chat.stream.errors.providerMediaSize'),
        'chat.stream.errors.providerMediaDecoding': i18n.t('chat.stream.errors.providerMediaDecoding'),
        'chat.stream.errors.providerMediaRetrieval': i18n.t('chat.stream.errors.providerMediaRetrieval'),
        'chat.stream.errors.providerContextUsage': i18n.t('chat.stream.errors.providerContextUsage', { requested: '{requested}', available: '{available}' }),
        'chat.stream.errors.context_budget_unavailable': i18n.t('chat.stream.errors.context_budget_unavailable'),
        'chat.stream.errors.contextBudgetUsage': i18n.t('chat.stream.errors.contextBudgetUsage', { context: '{context}', usable: '{usable}', reserved: '{reserved}' })
    };
};

export { buildChatStreamErrorTranslations, buildChatStreamClientErrorPresentation, buildChatStreamServerErrorPresentation, isChatStreamClientErrorCode, isChatStreamServerErrorCode, resolveChatStreamClientErrorBaseMessage, resolveChatStreamServerErrorBaseMessage, resolveChatStreamServerErrorMessage, resolveProviderExplanationText };
export type { ChatStreamClientErrorCode, ChatStreamServerErrorCode };
