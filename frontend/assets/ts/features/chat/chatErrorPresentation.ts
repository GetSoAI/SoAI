/* SoAI - Chat feature error presentation [frontend/assets/ts/features/chat/chatErrorPresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { extractUserFacingErrorMessage } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import { readNonNegativeIntegerOrNullValue } from '@core/types/payloadNumberReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isObject } from '@core/typeGuards.ts';

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

const resolveChatErrorDetailText = (value: Error | JsonValue | null | undefined): string | null => {
    if (value instanceof Error) {
        return extractUserFacingErrorMessage(value);
    }
    const presentation = readChatErrorPresentation(value);
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
    return extractUserFacingErrorMessage(value);
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

export { readChatErrorPresentation, resolveChatErrorDetailText, resolveChatRequestErrorNotificationMessage, resolveTokenCounterErrorNotificationMessage };
export type { ChatErrorPresentation, ChatErrorPromptBudgetDetails };
