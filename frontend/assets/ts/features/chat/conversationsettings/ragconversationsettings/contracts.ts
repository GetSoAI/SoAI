/* SoAI - Chat feature RAG conversation settings contracts [frontend/assets/ts/features/chat/conversationsettings/ragconversationsettings/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationSettingsHost, ConversationSettingsRagApi } from '@features/chat/conversationsettings/conversationSettingsHost.ts';
import { type RagConfig } from '@features/chat/conversationsettings/settingsModels.ts';
import type { RagConfigResponse } from '@core/api/contracts/webuiRagContracts.ts';

interface RagConfigUpdateCallbacks {
    updateSectionApplyState: (options: { baseline: RagConfig | null; current: RagConfig | null; hasChanges: (current: RagConfig, baseline: RagConfig) => boolean; isValid?: boolean | undefined }) => void;
    onBaselineConfigChange: (config: RagConfig | null) => void;
    applyConfigUpdates: (options: { conversationId: string; boundary: string; updateToken: () => number; isUpdateTokenActive: (token: number) => boolean; updateRequest: () => Promise<RagConfigResponse>; onAcceptedSuccess?: (payload: RagConfigResponse) => Promise<void> | void; onSuccess: (payload: RagConfigResponse) => void; onFinally?: () => void; successMessage: string; failureMessage: string; errorMessage: string }) => Promise<void>;
    onDirtyStateChange: (hasChanges: boolean) => void;
}

interface RagConversationSettingsControllerOptions {
    host: ConversationSettingsHost;
    api: ConversationSettingsRagApi;
    callbacks: RagConfigUpdateCallbacks;
}

export type { RagConversationSettingsControllerOptions, RagConfigUpdateCallbacks };
