/* SoAI - Chat page agent post-render maintenance controller [frontend/assets/ts/pages/chat/controllers/chatpageagent/AgentPostRenderMaintenanceController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatPageAgentHost } from '@pages/chat/controllers/chatpageagent/contracts.ts';
import type { ChatPageAgentState } from '@pages/chat/controllers/chatpageagent/state.ts';
import { drainPendingToolLiveProjectionUpdates } from '@pages/chat/controllers/chatpageagent/toolLiveProjectionDrainController.ts';

interface AgentPostRenderMaintenanceControllerArguments {
    host: ChatPageAgentHost;
    state: ChatPageAgentState;
    isDisposed(): boolean;
    reconcileActivityDurations(): void;
}

class AgentPostRenderMaintenanceController {
    #host: ChatPageAgentHost;
    #state: ChatPageAgentState;
    #isDisposed: () => boolean;
    #reconcileActivityDurations: () => void;

    constructor(inputArguments: AgentPostRenderMaintenanceControllerArguments) {
        this.#host = inputArguments.host;
        this.#state = inputArguments.state;
        this.#isDisposed = inputArguments.isDisposed;
        this.#reconcileActivityDurations = inputArguments.reconcileActivityDurations;
    }

    drainPendingToolLiveProjectionEvents(): void {
        drainPendingToolLiveProjectionUpdates(this.#host, this.#state, {
            isDisposed: this.#isDisposed,
            reconcileActivityDurations: this.#reconcileActivityDurations
        });
    }
}

export { AgentPostRenderMaintenanceController };
