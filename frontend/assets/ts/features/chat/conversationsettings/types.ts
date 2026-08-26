/* SoAI - Chat feature conversation settings public contracts [frontend/assets/ts/features/chat/conversationsettings/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationSettingsHost } from '@features/chat/conversationsettings/conversationSettingsHost.ts';

interface ChatConversationSettingsManagerDependencies {
    host: ConversationSettingsHost;
}

type ConversationSettingsSection = 'rag' | 'mcp' | 'identityPrompts' | 'workspace';

type ConversationSettingsActionState = {
    hasChanges: boolean;
    isValid: boolean;
    handler: (() => Promise<void>) | null;
} | null;

interface ConversationSettingsSectionState {
    ragDirty: boolean;
    ragValid: boolean;
    mcpDirty: boolean;
    identityPromptsDirty: boolean;
    workspaceDirty: boolean;
}

interface ConversationSettingsSectionActionHandlers {
    onApplyRagChanges: () => Promise<void>;
    onApplyMcpChanges: () => Promise<void>;
    onApplyIdentityPromptsChanges: () => Promise<void>;
    onApplyWorkspaceChanges: () => Promise<void>;
}

export type { ChatConversationSettingsManagerDependencies, ConversationSettingsActionState, ConversationSettingsSection, ConversationSettingsSectionActionHandlers, ConversationSettingsSectionState };
