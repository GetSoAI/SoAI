/* SoAI - Chat preset library invalidation contract [frontend/assets/ts/core/chat/chatPresetLibraryInvalidation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dispatchCustomEvent, getEventHub } from '@core/environment/public.ts';
import { requireStateManager } from '@core/state/runtime.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isObject } from '@core/typeGuards.ts';
import type { CrossTabPublishOutcome } from '@core/crosstab/channel.ts';

const CHAT_PRESET_LIBRARY_CHANNEL_ID = 'soai.webui.chat-presets';
const CHAT_PRESET_LIBRARY_INVALIDATED_EVENT = 'soai:webui:chat-presets-invalidated';
type ChatPresetLibraryInvalidationMessage = Readonly<{ version: 1; type: 'chat-presets-invalidated' }>;
const CHAT_PRESET_LIBRARY_INVALIDATION_MESSAGE: ChatPresetLibraryInvalidationMessage = Object.freeze({ version: 1, type: 'chat-presets-invalidated' });

const isChatPresetLibraryInvalidationMessage = (value: JsonValue | null | undefined): value is ChatPresetLibraryInvalidationMessage => {
    if (!isObject(value)) {
        return false;
    }
    const keys = Object.keys(value);
    return keys.length === 2 && keys.includes('version') && keys.includes('type') && value['version'] === 1 && value['type'] === 'chat-presets-invalidated';
};

const publishChatPresetLibraryInvalidation = (sameWindow: boolean): CrossTabPublishOutcome => {
    const outcome = requireStateManager().getCrossTabChannel(CHAT_PRESET_LIBRARY_CHANNEL_ID).publish(CHAT_PRESET_LIBRARY_INVALIDATION_MESSAGE);
    if (sameWindow) {
        dispatchCustomEvent(CHAT_PRESET_LIBRARY_INVALIDATED_EVENT, CHAT_PRESET_LIBRARY_INVALIDATION_MESSAGE);
    }
    return outcome;
};

const subscribeChatPresetLibraryInvalidation = (listener: () => void, includeSameWindow: boolean): (() => void) => {
    const unsubscribeCrossTab = requireStateManager()
        .getCrossTabChannel(CHAT_PRESET_LIBRARY_CHANNEL_ID)
        .subscribe((message) => {
            if (isChatPresetLibraryInvalidationMessage(message)) {
                listener();
            }
        });
    if (!includeSameWindow) {
        return unsubscribeCrossTab;
    }
    const eventHub = getEventHub();
    const handleSameWindow = (event: Event): void => {
        if (event instanceof CustomEvent && isChatPresetLibraryInvalidationMessage(event.detail)) {
            listener();
        }
    };
    eventHub.addEventListener(CHAT_PRESET_LIBRARY_INVALIDATED_EVENT, handleSameWindow);
    return (): void => {
        unsubscribeCrossTab();
        eventHub.removeEventListener(CHAT_PRESET_LIBRARY_INVALIDATED_EVENT, handleSameWindow);
    };
};

export { CHAT_PRESET_LIBRARY_CHANNEL_ID, CHAT_PRESET_LIBRARY_INVALIDATED_EVENT, isChatPresetLibraryInvalidationMessage, publishChatPresetLibraryInvalidation, subscribeChatPresetLibraryInvalidation };
export type { ChatPresetLibraryInvalidationMessage };
