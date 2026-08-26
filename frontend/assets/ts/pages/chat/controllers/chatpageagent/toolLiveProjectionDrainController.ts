/* SoAI - Chat page agent pending tool live projection draining [frontend/assets/ts/pages/chat/controllers/chatpageagent/toolLiveProjectionDrainController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import type { ChatPageAgentHost } from '@pages/chat/controllers/chatpageagent/contracts.ts';
import type { ChatPageAgentState } from '@pages/chat/controllers/chatpageagent/state.ts';
import { drainPendingToolCallLiveProjectionEvents } from '@pages/chat/controllers/chatpageagent/toolLiveProjectionEventsController.ts';

interface PendingToolLiveProjectionDrainOptions {
    isDisposed(): boolean;
    reconcileActivityDurations(): void;
}

const drainPendingToolLiveProjectionUpdates = (host: ChatPageAgentHost, state: ChatPageAgentState, options: PendingToolLiveProjectionDrainOptions): void => {
    if (state.pendingToolLiveProjectionEvents.size === 0) {
        return;
    }
    void host.workflow
        .runWithBoundary('chat.tool.live_projection.drain', async () => {
            const updated = await drainPendingToolCallLiveProjectionEvents(host, state.pendingToolLiveProjectionEvents, {
                isDisposed: () => options.isDisposed()
            });
            if (!updated) {
                return;
            }
            options.reconcileActivityDurations();
        })
        .catch((error) => {
            host.workflow.logWarning('Failed to drain pending tool live updates', ensureError(error));
        });
};

export { drainPendingToolLiveProjectionUpdates };
