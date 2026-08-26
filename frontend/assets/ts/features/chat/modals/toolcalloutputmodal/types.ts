/* SoAI - Chat feature tool call output modal contracts [frontend/assets/ts/features/chat/modals/toolcalloutputmodal/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';
import type { ToolCallLiveEventsPage } from '@core/api/contracts/chatRealtimeSnapshotContracts.ts';
import type { CopyActionDependencies } from '@features/chat/message/messageCopyNotifications.ts';

type ToolCallOutputModalToolCall = JsonObject;

type ToolCallOutputModalCopyText = {
    copyText: string;
};

type ToolCallOutputModalEscapeDependencies = {
    escapeHtml: <T>(value: T) => string;
    escapeAttribute: <T>(value: T) => string;
};

type ToolCallOutputModalCopyDependencies = CopyActionDependencies & {
    loadMoreLiveEvents: (beforeLiveSequence: number) => Promise<ToolCallLiveEventsPage>;
};

type ToolCallOutputModalDependencies = ToolCallOutputModalEscapeDependencies & ToolCallOutputModalCopyDependencies;

type ToolCallOutputModalContentElements = {
    contentElement: HTMLElement;
    copyButton: HTMLButtonElement;
};

type ToolCallOutputModalContentRender = ToolCallOutputModalCopyText & {
    html: string;
    nextBeforeLiveSequence: number | null;
};

export type { ToolCallOutputModalContentElements, ToolCallOutputModalContentRender, ToolCallOutputModalCopyDependencies, ToolCallOutputModalCopyText, ToolCallOutputModalDependencies, ToolCallOutputModalEscapeDependencies, ToolCallOutputModalToolCall };
