/* SoAI - Assistant keyed DOM patch contracts [frontend/assets/ts/features/chat/message/assistantKeyedPatchContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AssistantDomStatePreservation } from '@features/chat/message/assistantDomState.ts';
import type { AssistantKeyedPatchPolicy } from '@features/chat/message/assistantKeyedPatchPolicy.ts';
import type { AssistantBodySignatureKind } from '@features/chat/message/assistantMessageMarkupParts.ts';
import type { ActivityPatchHandler } from '@features/chat/message/assistantNestedActivityPatching.ts';

type SegmentSignatureMap = Map<string, string>;

type StreamChildItem = {
    key: string;
    signature: string;
    markup?: string | undefined;
    element?: HTMLElement | undefined;
    signatureKind?: AssistantBodySignatureKind;
};

type PatchStreamingKeyedChildrenArguments = {
    container: HTMLElement;
    items: StreamChildItem[];
    cachedMarkupByKey: Map<string, string> | null;
    cachedSignatureByKey: SegmentSignatureMap | null;
    policy?: AssistantKeyedPatchPolicy;
    assistantDomState?: AssistantDomStatePreservation | null;
    patchExistingChild: ActivityPatchHandler;
    setCachedMarkupByKey?: (map: Map<string, string>) => void;
    setCachedSignatureByKey?: (map: SegmentSignatureMap) => void;
};

type AssistantKeyedPatchResult = {
    supported: boolean;
    updated: boolean;
    changedElements: HTMLElement[];
};

const createUnchangedAssistantKeyedPatchResult = (): AssistantKeyedPatchResult => ({
    supported: true,
    updated: false,
    changedElements: []
});

const createUpdatedAssistantKeyedPatchResult = (changedElements: HTMLElement[]): AssistantKeyedPatchResult => ({
    supported: true,
    updated: true,
    changedElements
});

const createUnsupportedAssistantKeyedPatchResult = (): AssistantKeyedPatchResult => ({
    supported: false,
    updated: false,
    changedElements: []
});

export { createUnchangedAssistantKeyedPatchResult, createUnsupportedAssistantKeyedPatchResult, createUpdatedAssistantKeyedPatchResult };
export type { AssistantKeyedPatchResult, PatchStreamingKeyedChildrenArguments, StreamChildItem };
