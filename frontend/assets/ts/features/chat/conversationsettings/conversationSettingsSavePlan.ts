/* SoAI - Captured conversation settings save operations [frontend/assets/ts/features/chat/conversationsettings/conversationSettingsSavePlan.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isChatConversationSettingsWritable } from '@features/chat/conversation/conversationSettingsEligibility.ts';
import { reconcileMcpIntentAfterKnowledge } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/mcpPresetStaging.ts';
import type { ConversationSettingsControllerBundle } from '@features/chat/conversationsettings/controllerRegistry.ts';
import type { ConversationSettingsHost, ConversationSettingsSavePlanInput } from '@features/chat/conversationsettings/conversationSettingsHost.ts';
import type { ConversationSettingsSectionState } from '@features/chat/conversationsettings/types.ts';

const buildConversationSettingsSavePlan = (host: ConversationSettingsHost, controllers: ConversationSettingsControllerBundle | null, sectionState: ConversationSettingsSectionState, conversationId: string | null, isPresentationActive: () => boolean): ConversationSettingsSavePlanInput => {
    const identityDirty = sectionState.identityPromptsDirty;
    const workspaceDirty = sectionState.workspaceDirty;
    const knowledgeDirty = sectionState.ragDirty;
    const ragIntent = controllers?.ragController.workingConfig() ?? null;
    const ragOperation = controllers?.ragController.prepareConfigApply(ragIntent, isPresentationActive) ?? null;
    const capturedConversation = host.data.getCurrentConversation();
    const workspaceOperation = workspaceDirty && controllers ? controllers.workspacePathController.prepareConversationSave(isPresentationActive) : null;
    const mcpIntent = controllers?.mcpController.workingValues() ?? null;
    const mcpBaseline = controllers?.mcpController.baselineConfig() ?? null;
    const mcpConversationId = conversationId;
    const mcpAcceptedWritable = mcpConversationId !== null && capturedConversation?.id === mcpConversationId && isChatConversationSettingsWritable(capturedConversation);
    const mcpOperation = controllers?.mcpController.prepareConfigApply(mcpIntent, mcpBaseline, mcpConversationId, isPresentationActive, mcpAcceptedWritable) ?? null;
    return {
        conversation:
            identityDirty || workspaceDirty
                ? {
                      hasChanges: true,
                      isValid: controllers?.identityPromptsController.isValid() !== false && controllers?.workspacePathController.isValid() !== false,
                      handler: async () => {
                          if (!controllers) return;
                          if (identityDirty && isPresentationActive() && host.data.getCurrentConversation() === capturedConversation) controllers.identityPromptsController.finalizeConversationSave();
                          if (workspaceOperation && !(await workspaceOperation())) return { type: 'continue-degraded' };
                          return;
                      }
                  }
                : null,
        knowledge: knowledgeDirty ? { hasChanges: true, isValid: sectionState.ragValid, handler: ragOperation ? async () => ((await ragOperation()) ? undefined : { type: 'continue-degraded' }) : null } : null,
        skills: sectionState.skillsDirty ? { hasChanges: true, isValid: sectionState.skillsValid, handler: controllers?.skillsController.prepareSave(isPresentationActive) ?? null } : null,
        tools: sectionState.mcpDirty
            ? {
                  hasChanges: true,
                  isValid: true,
                  handler: controllers
                      ? async () => {
                            let intent = mcpIntent;
                            let skipped = 0;
                            let degraded = false;
                            if (knowledgeDirty && intent && mcpBaseline) {
                                const refreshed = await controllers.mcpController.refreshKnowledgeManagedState(mcpConversationId);
                                const reconciled = reconcileMcpIntentAfterKnowledge(intent, mcpBaseline, refreshed.config, refreshed.tools);
                                intent = reconciled.values;
                                skipped = reconciled.skippedValues.length;
                                degraded = !(await controllers.mcpController.prepareConfigApply(intent, refreshed.config, mcpConversationId, isPresentationActive, mcpAcceptedWritable)());
                            } else {
                                degraded = Boolean(mcpOperation && !(await mcpOperation()));
                            }
                            return skipped > 0 || degraded ? { type: 'continue-degraded' } : undefined;
                        }
                      : null
              }
            : null
    };
};

export { buildConversationSettingsSavePlan };
