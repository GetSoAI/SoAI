/* SoAI - Shared layout chat streaming watcher [frontend/assets/ts/core/layout/sidebar/chatStreamingWatcher.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseChatStreamActivityResource } from '@core/chat/chatStreamActivitySnapshot.ts';
import type { SidebarBusyIndicatorRegistry } from '@core/layout/sidebar/busyIndicatorRegistry.ts';
import { getStreamSubscriptions } from '@core/realtime/streammanager/streamManagerAccess.ts';
import { WEBUI_CHAT_ACTIVITY } from '@core/realtime/streammanager/resources/ids.ts';

const CHAT_STREAM_ACTIVITY_SOURCE = 'chat-stream-activity';

const subscribeChatStreamingWatcher = (busyIndicatorRegistry: SidebarBusyIndicatorRegistry): (() => void) => {
    const unsubscribe = getStreamSubscriptions().subscribeResourceValue(WEBUI_CHAT_ACTIVITY, (value) => {
        const activity = parseChatStreamActivityResource(value);
        busyIndicatorRegistry.setBusy('chat', CHAT_STREAM_ACTIVITY_SOURCE, activity.activeConversationIds.length > 0);
    });
    return (): void => {
        unsubscribe();
        busyIndicatorRegistry.setBusy('chat', CHAT_STREAM_ACTIVITY_SOURCE, false);
    };
};

export { subscribeChatStreamingWatcher };
