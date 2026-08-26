/* SoAI - Chat feature operations [frontend/assets/ts/features/chat/conversationsettings/ragconversationsettings/service/operations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { parseRagConfig } from '@features/chat/conversationsettings/conversationSettingsParsing.ts';
import type { ConversationSettingsRagApi } from '@features/chat/conversationsettings/conversationSettingsHost.ts';
import { computeRagConfigUpdatePayload } from '@features/chat/conversationsettings/ragconversationsettings/state.ts';
import type { RagConfig } from '@features/chat/conversationsettings/settingsModels.ts';
import type { RagConfigUpdateCallbacks } from '@features/chat/conversationsettings/ragconversationsettings/contracts.ts';
import type { RagConfigResponse } from '@core/api/contracts/webuiRagContracts.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface RagConfigApplyResult {
    active: boolean;
    reconciled: boolean;
    response: RagConfigResponse | null;
}

interface ApplyRagConversationConfigChangesOptions {
    api: ConversationSettingsRagApi;
    callbacks: RagConfigUpdateCallbacks;
    conversationId: string | null;
    baseline: RagConfig | null;
    current: RagConfig | null;
    updateToken: () => number;
    isUpdateTokenActive: (token: number) => boolean;
    onConfigApplied: (config: RagConfig) => boolean;
    onStateUpdated: () => void;
    projectDefaults: (response: RagConfigResponse) => Promise<boolean>;
    publishInvalidation: () => void;
}

const applyRagConversationConfigChanges = async (options: ApplyRagConversationConfigChangesOptions): Promise<RagConfigApplyResult> => {
    const { conversationId, baseline, current } = options;
    if (!conversationId || !baseline || !current) {
        return { active: false, reconciled: true, response: null };
    }
    const updates = computeRagConfigUpdatePayload({ baseline, current });
    if (Object.keys(updates).length === 0) {
        options.onStateUpdated();
        return { active: true, reconciled: true, response: null };
    }
    let mirrorReconciled = true;
    let presentationReconciled = true;
    let active = false;
    let response: RagConfigResponse | null = null;
    await options.callbacks.applyConfigUpdates({
        conversationId,
        updateToken: options.updateToken,
        isUpdateTokenActive: options.isUpdateTokenActive,
        boundary: 'chat:ragUpdate',
        updateRequest: async () => {
            const response = await options.api.updateConfig(conversationId, updates);
            options.publishInvalidation();
            return response;
        },
        onAcceptedSuccess: async (payload) => {
            response = payload;
            try {
                mirrorReconciled = await options.projectDefaults(payload);
            } catch (error) {
                mirrorReconciled = false;
                errorHandler.warn('ChatConversationSettings', 'RAG preference projection failed after commit', ensureError(error));
            }
        },
        onSuccess: (payload) => {
            active = true;
            try {
                presentationReconciled = options.onConfigApplied(parseRagConfig(payload));
            } catch (error) {
                presentationReconciled = false;
                errorHandler.warn('ChatConversationSettings', 'RAG presentation projection failed after commit', ensureError(error));
            }
        },
        successMessage: i18n.t('chat.configuration.notifications.ragUpdateSuccess'),
        failureMessage: i18n.t('chat.configuration.notifications.ragUpdateFailed'),
        errorMessage: 'Failed to update RAG config'
    });
    return { active, reconciled: mirrorReconciled && presentationReconciled, response };
};

export { applyRagConversationConfigChanges };
export type { ApplyRagConversationConfigChangesOptions, RagConfigApplyResult };
