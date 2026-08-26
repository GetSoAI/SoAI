/* SoAI - Chat page conversation operation execution controller [frontend/assets/ts/pages/chat/controllers/chatconversationactionscontroller/conversationOperationExecutionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { runConversationActionOperation } from '@pages/chat/controllers/chatconversationactionscontroller/service.ts';
import type { ChatConversationActionsControllerRuntime } from '@pages/chat/controllers/chatconversationactionscontroller/types.ts';
import type { ConversationOperationsDependencies } from '@pages/chat/controllers/chatconversationactionscontroller/operations.ts';

const NAVIGATION_OPERATION_ID = 'chat:conversationNavigation';
const CONVERSATION_SWITCH_OPERATION_ID = 'chat:conversationSwitch';
const CONVERSATION_SETTINGS_AUTHORITY_REFRESH_OPERATION_ID = 'chat:conversationSettingsAuthorityRefresh';

interface EnqueueConversationOperationOptions {
    scope: string;
    task: () => Promise<void>;
    logMessage: string;
    errorMessage: string;
    shouldNotifyError?: () => boolean;
}

const completeDraftTransfer = async (draftTransfer: { complete(): Promise<void>; cancel(): void } | null): Promise<void> => {
    if (draftTransfer === null) {
        return;
    }
    try {
        await draftTransfer.complete();
    } finally {
        draftTransfer.cancel();
    }
};

const createOperationDependencies = (runtime: ChatConversationActionsControllerRuntime): ConversationOperationsDependencies => ({
    host: runtime.host,
    state: runtime.state,
    conversationManager: runtime.conversationManager,
    storageManager: runtime.storageManager,
    uiManager: runtime.uiManager,
    chatStreamingController: runtime.chatStreamingController,
    getConversationSettingsManager: () => runtime.conversationSettingsManager
});

const enqueueOperation = (runtime: ChatConversationActionsControllerRuntime, operationId: string, options: EnqueueConversationOperationOptions): void => {
    runtime.host.workflow.runUiTask(operationId, async () => {
        await runConversationActionOperation({
            host: runtime.host,
            scope: options.scope,
            task: options.task,
            logMessage: options.logMessage,
            errorMessage: options.errorMessage,
            ...(options.shouldNotifyError ? { shouldNotifyError: options.shouldNotifyError } : {})
        });
    });
};

export { CONVERSATION_SETTINGS_AUTHORITY_REFRESH_OPERATION_ID, CONVERSATION_SWITCH_OPERATION_ID, NAVIGATION_OPERATION_ID, completeDraftTransfer, createOperationDependencies, enqueueOperation };
