/* SoAI - Agent plan execution handoff from the chat plan widget [frontend/assets/ts/pages/chat/controllers/page/actions/agentPlanExecutionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AgentMode } from '@core/chat/agentMode.ts';
import { i18n } from '@core/i18n/index.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

interface AgentPlanExecutionHost extends PageFeedbackOwnerHost {
    getCurrentConversationId(): string | null;
    isConversationExecuting(conversationId: string): boolean;
    resolveModeForConversation(conversationId: string): AgentMode;
    selectMode(mode: AgentMode): void;
    waitForPendingModeUpdate(): Promise<void>;
    sendTextMessage(text: string): Promise<void>;
}

const EXECUTE_MODE: AgentMode = 'execute';

const startAgentPlanExecution = async (host: AgentPlanExecutionHost): Promise<void> => {
    const conversationId = host.getCurrentConversationId();
    if (!conversationId) {
        return;
    }
    if (host.isConversationExecuting(conversationId)) {
        host.feedback.show(i18n.t('chat.planWidget.executeBusy'), 'info');
        return;
    }
    if (host.resolveModeForConversation(conversationId) !== EXECUTE_MODE) {
        host.selectMode(EXECUTE_MODE);
        await host.waitForPendingModeUpdate();
        if (host.resolveModeForConversation(conversationId) !== EXECUTE_MODE) {
            host.feedback.show(i18n.t('chat.planWidget.executeUnavailable'), 'warning');
            return;
        }
    }
    await host.sendTextMessage(i18n.t('chat.planWidget.executePrompt'));
};

export { startAgentPlanExecution };
export type { AgentPlanExecutionHost };
