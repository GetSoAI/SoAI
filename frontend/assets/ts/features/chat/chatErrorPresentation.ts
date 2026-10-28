/* SoAI - Chat feature error presentation [frontend/assets/ts/features/chat/chatErrorPresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveOperationCauseMessage } from '@core/errors/operationCausePresentation.ts';
import { extractErrorCode, extractUserFacingErrorMessage } from '@core/errors/coerce.ts';
import { resolveSkillErrorMessage } from '@core/skills/errorPresentation.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import { readNonNegativeIntegerOrNullValue } from '@core/types/payloadNumberReaders.ts';
import { isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isNonNegativeInteger, isObject, isPositiveInteger } from '@core/typeGuards.ts';

interface ChatErrorPromptBudgetDetails {
    type: 'prompt_budget_exceeded' | 'prompt_budget_capped';
    promptTokens: number | null;
    budgetTokens: number | null;
}

interface ChatErrorPresentation {
    code: string | null;
    message: string | null;
    userMessage: string | null;
    promptBudget: ChatErrorPromptBudgetDetails | null;
}

const parsePromptBudgetDetails = (value: JsonValue | null | undefined): ChatErrorPromptBudgetDetails | null => {
    if (!isObject(value)) {
        return null;
    }
    const type = value['type'];
    if (type !== 'prompt_budget_exceeded' && type !== 'prompt_budget_capped') {
        return null;
    }
    return {
        type,
        promptTokens: readNonNegativeIntegerOrNullValue(value['prompt_tokens']),
        budgetTokens: readNonNegativeIntegerOrNullValue(value['budget_tokens'])
    };
};

const readChatErrorPresentation = (value: JsonValue | null | undefined): ChatErrorPresentation => {
    if (!isObject(value)) {
        return {
            code: null,
            message: null,
            userMessage: null,
            promptBudget: null
        };
    }
    return {
        code: toTrimmedStringOrNull(value['code']),
        message: toTrimmedStringOrNull(value['message']),
        userMessage: toTrimmedStringOrNull(value['user_message']),
        promptBudget: parsePromptBudgetDetails(value['details'])
    };
};

const resolveContextUsageMessage = (details: JsonValue | null | undefined): string => {
    const guidance = i18n.t('chat.stream.errors.providerContext');
    if (isJsonObject(details) && details['token_scope'] === 'prompt') {
        return resolveOperationCauseMessage('context_window_exceeded', { details }) ?? guidance;
    }
    if (isJsonObject(details) && isPositiveInteger(details['requested_tokens']) && isPositiveInteger(details['available_tokens'])) {
        return `${i18n.t('chat.stream.errors.providerContextUsage', { requested: details['requested_tokens'], available: details['available_tokens'] })} ${guidance}`;
    }
    return guidance;
};

const resolveContextBudgetErrorMessage = (code: string | null, details: JsonValue | null | undefined): string | null => {
    const type = isJsonObject(details) ? details['type'] : null;
    if (type === 'context_window_exceeded') {
        return resolveContextUsageMessage(details);
    }
    if (code !== 'context_budget_unavailable' && type !== 'context_budget_unavailable') {
        return null;
    }
    const guidance = i18n.t('chat.stream.errors.context_budget_unavailable');
    if (isJsonObject(details) && isPositiveInteger(details['context_window_tokens']) && isPositiveInteger(details['usable_context_tokens']) && isNonNegativeInteger(details['reserved_output_tokens'])) {
        return `${i18n.t('chat.stream.errors.contextBudgetUsage', { context: details['context_window_tokens'], usable: details['usable_context_tokens'], reserved: details['reserved_output_tokens'] })} ${guidance}`;
    }
    return guidance;
};

const resolveChatErrorDetailText = (value: Error | JsonValue | null | undefined): string | null => {
    const skillMessage = resolveSkillErrorMessage(extractErrorCode(value), value);
    if (skillMessage) return skillMessage;
    if (value instanceof Error) {
        return resolveOperationCauseMessage(extractErrorCode(value), value) ?? extractUserFacingErrorMessage(value);
    }
    const presentation = readChatErrorPresentation(value);
    const contextMessage = resolveContextBudgetErrorMessage(presentation.code, isObject(value) ? value['details'] : null);
    if (contextMessage !== null) {
        return contextMessage;
    }
    const promptBudget = presentation.promptBudget;
    if (promptBudget !== null && promptBudget.type === 'prompt_budget_exceeded' && promptBudget.promptTokens !== null && promptBudget.budgetTokens !== null) {
        return i18n.t('chat.notifications.promptBudgetExceeded', {
            promptTokens: promptBudget.promptTokens,
            budgetTokens: promptBudget.budgetTokens
        });
    }
    if (promptBudget !== null && promptBudget.type === 'prompt_budget_capped' && promptBudget.budgetTokens !== null) {
        return i18n.t('chat.notifications.promptBudgetCapped', {
            budgetTokens: promptBudget.budgetTokens
        });
    }
    return resolveOperationCauseMessage(presentation.code, value) ?? extractUserFacingErrorMessage(value);
};

const resolveChatRequestErrorNotificationMessage = (inputArguments: { error: Error | JsonValue | null | undefined; title: string | null }): string => {
    const detail = resolveChatErrorDetailText(inputArguments.error);
    if (inputArguments.title && detail) {
        return i18n.t('chat.notifications.requestFailedDetail', { title: inputArguments.title, detail });
    }
    if (inputArguments.title) {
        return i18n.t('chat.notifications.requestFailed', { title: inputArguments.title });
    }
    return detail ? i18n.t('chat.status.requestFailed', { message: detail }) : i18n.t('chat.stream.failedToGetResponse');
};

const resolveTokenCounterErrorNotificationMessage = (error: Error | JsonValue | null | undefined): string => {
    const detail = resolveChatErrorDetailText(error);
    if (detail) {
        return i18n.t('chat.tokenCounter.countFailedDetail', { detail });
    }
    return i18n.t('chat.tokenCounter.countFailed');
};

export { readChatErrorPresentation, resolveChatErrorDetailText, resolveChatRequestErrorNotificationMessage, resolveContextBudgetErrorMessage, resolveContextUsageMessage, resolveTokenCounterErrorNotificationMessage };
export type { ChatErrorPresentation, ChatErrorPromptBudgetDetails };
