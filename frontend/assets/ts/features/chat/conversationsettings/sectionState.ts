/* SoAI - Chat feature section state [frontend/assets/ts/features/chat/conversationsettings/sectionState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationSettingsSectionState } from '@features/chat/conversationsettings/types.ts';

const createDefaultSectionState = (): ConversationSettingsSectionState => ({
    ragDirty: false,
    ragValid: true,
    mcpDirty: false,
    identityPromptsDirty: false,
    workspaceDirty: false
});

export { createDefaultSectionState };
