/* SoAI - Frontend application session services [frontend/assets/ts/app/bootstrap/stages/sessionServices.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireAiSetupAttentionLifecycle } from '@core/aisetup/serviceAccess.ts';
import { requireAutomationRunActivityLifecycle } from '@core/automation/serviceAccess.ts';
import { requireChatConversationAttention, requireChatStreamServiceLifecycle } from '@core/chat/streamServiceAccess.ts';

const initializeAuthenticatedSessionServices = async (): Promise<void> => {
    requireChatStreamServiceLifecycle().initialize();
    await requireChatConversationAttention().initialize();
    await requireAutomationRunActivityLifecycle().initialize();
    requireAiSetupAttentionLifecycle().initialize();
};

const resetAuthenticatedSessionServices = async (): Promise<void> => {
    requireChatStreamServiceLifecycle().dispose();
    requireChatConversationAttention().dispose();
    requireAiSetupAttentionLifecycle().dispose();
    await requireAutomationRunActivityLifecycle().destroy();
};

export { initializeAuthenticatedSessionServices, resetAuthenticatedSessionServices };
