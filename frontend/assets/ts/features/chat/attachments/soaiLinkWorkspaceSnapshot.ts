/* SoAI - Chat SoAI link workspace snapshot helpers [frontend/assets/ts/features/chat/attachments/soaiLinkWorkspaceSnapshot.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedStringOrNull } from '@core/normalize.ts';
import type { Conversation } from '@features/chat/storage/storageModels.ts';

type SoaiLinkWorkspaceSnapshot = {
    conversationId: string;
    workspacePath: string | null;
    workspaceRootFingerprint: string | null;
};

const captureSoaiLinkWorkspaceSnapshot = (conversation: Conversation | null): SoaiLinkWorkspaceSnapshot | null => {
    if (conversation === null) {
        return null;
    }
    return {
        conversationId: conversation.id,
        workspacePath: toTrimmedStringOrNull(conversation.modelSettings.workspacePath),
        workspaceRootFingerprint: toTrimmedStringOrNull(conversation.effectiveWorkspaceRootFingerprint)
    };
};

const matchesSoaiLinkWorkspaceSnapshot = (conversation: Conversation | null, snapshot: SoaiLinkWorkspaceSnapshot | null): boolean => {
    if (conversation === null || snapshot === null) {
        return false;
    }
    return conversation.id === snapshot.conversationId && toTrimmedStringOrNull(conversation.modelSettings.workspacePath) === snapshot.workspacePath && toTrimmedStringOrNull(conversation.effectiveWorkspaceRootFingerprint) === snapshot.workspaceRootFingerprint;
};

export { captureSoaiLinkWorkspaceSnapshot, matchesSoaiLinkWorkspaceSnapshot };
export type { SoaiLinkWorkspaceSnapshot };
