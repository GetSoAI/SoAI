/* SoAI - Chat feature event binding runtime [frontend/assets/ts/features/chat/conversationsettings/ragconversationsettings/service/eventBindingRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationSettingsHost } from '@features/chat/conversationsettings/conversationSettingsHost.ts';
import { bindRagConversationControllerEvents } from '@features/chat/conversationsettings/ragconversationsettings/service/events.ts';
import type { RagConversationSettingsViewBindings } from '@features/chat/conversationsettings/ragconversationsettings/service/viewBindings.ts';

interface BindRagControllerRuntimeArguments {
    modal: Element;
    host: ConversationSettingsHost;
    view: RagConversationSettingsViewBindings;
    updateApplyState: () => void;
}

const bindRagControllerRuntime = (inputArguments: BindRagControllerRuntimeArguments): Array<() => void> => {
    inputArguments.view.setModal(inputArguments.modal);
    return bindRagConversationControllerEvents({
        modal: inputArguments.modal,
        host: inputArguments.host,
        updateApplyState: () => inputArguments.updateApplyState()
    });
};

export { bindRagControllerRuntime };
