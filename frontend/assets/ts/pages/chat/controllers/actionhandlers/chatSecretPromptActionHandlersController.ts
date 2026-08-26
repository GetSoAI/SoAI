/* SoAI - Chat page secret prompt action handlers controller [frontend/assets/ts/pages/chat/controllers/actionhandlers/chatSecretPromptActionHandlersController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SecretPromptInteractionResolutionRequest } from '@core/api/contracts/webuiChatOperationContracts.ts';
import { readTrimmedInputValue } from '@core/dom/formValues.ts';
import { CHAT_ACTIONS, optionalSecretPromptInput, optionalSecretPromptRootFromChild, optionalSecretPromptSaveCheckbox } from '@features/chat/public.ts';
import { createResolvedNamedTaskActionHandler, createResolvedTaskPayloadActionHandler, type TaskActionResolutionHost } from '@pages/chat/controllers/actionhandlers/taskActionResolutionController.ts';
import type { ChatComposerActionPort } from '@pages/chat/controllers/actionhandlers/core/contracts.ts';

type ChatActionHandler = (actionElement: HTMLElement, event: Event) => void;

type ChatSecretPromptActionId = typeof CHAT_ACTIONS.SECRET_PROMPT_SUBMIT | typeof CHAT_ACTIONS.SECRET_PROMPT_CANCEL;

type ChatSecretPromptActionHandlersHost = TaskActionResolutionHost & { composer: Pick<ChatComposerActionPort, 'resolveSecret'> };

const buildSubmitRequest = (root: HTMLElement): SecretPromptInteractionResolutionRequest => {
    const usernameInput = optionalSecretPromptInput(root, 'username');
    const username = usernameInput ? readTrimmedInputValue(usernameInput) : '';
    const password = optionalSecretPromptInput(root, 'password')?.value ?? '';
    const saveToVault = optionalSecretPromptSaveCheckbox(root)?.checked === true;
    const labelInput = optionalSecretPromptInput(root, 'label');
    const label = labelInput ? readTrimmedInputValue(labelInput) : '';
    if (saveToVault && !label) {
        throw new Error('Label is required when saving to vault.');
    }
    return {
        action: 'submit',
        username: username ? username : null,
        password: password,
        saveToVault,
        label: label ? label : null
    };
};

const createSecretPromptCancelAction = (host: ChatSecretPromptActionHandlersHost): ((actionElement: HTMLElement) => void) => {
    return createResolvedNamedTaskActionHandler(host, 'chat:secretPromptCancel', 'Chat secret-prompt cancel action requires data-task-id', 'cancel', async (conversationId, taskId) => {
        await host.composer.resolveSecret(conversationId, taskId, { action: 'cancel' });
    });
};

const createChatSecretPromptActionHandlers = (host: ChatSecretPromptActionHandlersHost): Record<ChatSecretPromptActionId, ChatActionHandler> => {
    const cancelAction = createSecretPromptCancelAction(host);
    const submitAction = createResolvedTaskPayloadActionHandler(
        host,
        'chat:secretPromptSubmit',
        'Chat secret-prompt submit action requires data-task-id',
        (actionElement) => {
            const root = optionalSecretPromptRootFromChild(actionElement);
            if (!root) {
                return null;
            }
            return buildSubmitRequest(root);
        },
        async (conversationId, taskId, payload) => {
            await host.composer.resolveSecret(conversationId, taskId, payload);
        }
    );
    return {
        [CHAT_ACTIONS.SECRET_PROMPT_SUBMIT]: submitAction,
        [CHAT_ACTIONS.SECRET_PROMPT_CANCEL]: cancelAction
    };
};

export { createChatSecretPromptActionHandlers };
