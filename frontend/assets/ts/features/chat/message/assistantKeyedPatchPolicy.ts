/* SoAI - Assistant keyed patch policy for chat message DOM reconciliation [frontend/assets/ts/features/chat/message/assistantKeyedPatchPolicy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type AssistantKeyedPatchPolicy = {
    nonReplaceableKeys: ReadonlySet<string> | null;
    disableInsertAnimation: boolean;
    applyStreamingReveal: boolean;
    applyStreamingRevealToTextBlocks: boolean;
};

const DEFAULT_ASSISTANT_KEYED_PATCH_POLICY: AssistantKeyedPatchPolicy = {
    nonReplaceableKeys: null,
    disableInsertAnimation: false,
    applyStreamingReveal: false,
    applyStreamingRevealToTextBlocks: false
};

const resolveAssistantKeyedPatchPolicy = (policy: AssistantKeyedPatchPolicy | undefined): AssistantKeyedPatchPolicy => policy ?? DEFAULT_ASSISTANT_KEYED_PATCH_POLICY;

export { resolveAssistantKeyedPatchPolicy };
export type { AssistantKeyedPatchPolicy };
