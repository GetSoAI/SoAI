/* SoAI - Shell stop message action [frontend/assets/ts/features/chat/message/shell/stopAction.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { isString } from '@core/typeGuards.ts';
import type { ConversationContract } from '@features/chat/ChatTypes.ts';
import type { ChatMessageActionData, ChatMessageActionsDependencies } from '@features/chat/message/actionDeps.ts';
import { resolveToolCallActionIdentity } from '@features/chat/message/toolCallActionIdentity.ts';

const INLINE_ACTIVITY_STOP_BUTTON_CLASS = 'inline-activity-stop-button';
const INLINE_ACTIVITY_STOP_REQUESTED_ATTRIBUTE = 'data-inline-activity-stop-requested';

const setStopButtonDisabled = (data: ChatMessageActionData | undefined, disabled: boolean): void => {
    const element = data?.actionElement;
    if (!(element instanceof HTMLButtonElement)) {
        return;
    }
    element.disabled = disabled;
    element.setAttribute('aria-disabled', disabled ? 'true' : 'false');
};

const removeHeaderStopButton = (data: ChatMessageActionData | undefined): void => {
    const element = data?.actionElement;
    if (!(element instanceof HTMLButtonElement) || !element.classList.contains(INLINE_ACTIVITY_STOP_BUTTON_CLASS)) {
        return;
    }
    const activity = element.closest('.inline-activity');
    if (activity instanceof HTMLElement) {
        activity.setAttribute(INLINE_ACTIVITY_STOP_REQUESTED_ATTRIBUTE, 'true');
    }
    element.remove();
};

const stopShell = async (dependencies: ChatMessageActionsDependencies, conversation: ConversationContract, data: ChatMessageActionData | undefined): Promise<void> => {
    const conversationId = isString(conversation.id) && conversation.id.trim() ? conversation.id.trim() : '';
    const identity = resolveToolCallActionIdentity(data);
    if (!conversationId || identity === null) {
        dependencies.interaction.showNotification(i18n.t('chat.toolActivity.stopShellFailed'), 'error');
        return;
    }
    setStopButtonDisabled(data, true);
    try {
        const response = await dependencies.runtime.stopShell({
            conversationId,
            assistantTurnAtMs: identity.assistantTurnAtMs,
            modelVariantIndex: identity.modelVariantIndex,
            toolCallId: identity.toolCallId
        });
        if (response.status === 'already_terminal') {
            await dependencies.runtime.loadConversationMessages(conversationId, { force: true });
            dependencies.runtime.invalidateChatMarkup('both');
            await dependencies.runtime.renderCurrentConversation();
        }
        removeHeaderStopButton(data);
        dependencies.interaction.showNotification(i18n.t('chat.toolActivity.stopShellRequested'), 'info');
    } catch (error) {
        setStopButtonDisabled(data, false);
        dependencies.runtime.reportRequestFailure(ensureError(error));
    }
};

export { stopShell };
