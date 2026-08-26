/* SoAI - Chat feature service events [frontend/assets/ts/features/chat/conversationsettings/ragconversationsettings/service/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationSettingsHost } from '@features/chat/conversationsettings/conversationSettingsHost.ts';
import { bindRagConversationEvents } from '@features/chat/conversationsettings/ragconversationsettings/dom.ts';
import { updateRagToggleState } from '@features/chat/conversationsettings/ragconversationsettings/view.ts';

interface BindRagConversationControllerEventsOptions {
    modal: Element;
    host: ConversationSettingsHost;
    updateApplyState: () => void;
}

const bindRagConversationControllerEvents = (options: BindRagConversationControllerEventsOptions): Array<() => void> => {
    return bindRagConversationEvents(options.modal, (target, eventName, handler) => options.host.view.on(target, eventName, handler), {
        onConfigInputChange: () => {
            options.updateApplyState();
        },
        onConfigInputToggle: (element) => {
            updateRagToggleState(element);
            options.updateApplyState();
        }
    });
};

export { bindRagConversationControllerEvents };
export type { BindRagConversationControllerEventsOptions };
