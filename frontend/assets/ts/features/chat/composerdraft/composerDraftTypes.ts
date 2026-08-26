/* SoAI - Chat composer draft types [frontend/assets/ts/features/chat/composerdraft/composerDraftTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationDraftResponse, ConversationDraftSaveRequest } from '@core/api/contracts/chatQueueDraftContracts.ts';
import type { RequestOptions } from '@core/api/types/request.ts';
import type { ConversationDraftChangedEvent } from '@core/realtime/eventcontracts/chatControlContracts.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { ChatAttachment } from '@features/chat/ChatTypes.ts';
import type { ChatAttachmentManager } from '@features/chat/ChatAttachmentManager.ts';
import type { SoaiPathDraftRecord } from '@features/chat/attachments/soaiPathDraftRecords.ts';

interface ComposerDraftApi {
    get(conversationId: string, options?: RequestOptions): Promise<ConversationDraftResponse>;
    save(conversationId: string, payload: ConversationDraftSaveRequest, options?: RequestOptions): Promise<ConversationDraftResponse>;
    delete(conversationId: string, options?: RequestOptions): Promise<ConversationDraftResponse>;
}

interface ComposerDraftManagerDependencies {
    api: ComposerDraftApi;
    getCurrentConversationId(): string | null;
    isConversationPersisted(conversationId: string): boolean;
    readText(): string;
    readSourceText(): string;
    setText(value: string): void;
    attachmentManager: Pick<ChatAttachmentManager, 'getAttachments' | 'getDraftRevision' | 'subscribeDraftChanges' | 'checkoutAttachments' | 'restoreAttachments' | 'addResolvedSoaiPathRecords'>;
    refreshComposerUi(): void;
    noteInputDraftChanged(value: string): void;
    validateSourceProjection(text: string, sourceText: string, records: readonly SoaiPathDraftRecord[]): void;
    restoreSourceProjection(text: string, sourceText: string, records: readonly SoaiPathDraftRecord[]): void;
    showNotification(message: string, type: NotificationType): void;
    logWarning(message: string, error: Error): void;
    subscribeDraftChanged(listener: (event: ConversationDraftChangedEvent) => void): () => void;
    setTimer(functionValue: () => void, delay: number): number | null;
    clearTimer(timer: number | null): void;
}

interface ComposerDraftProjection {
    conversationId: string | null;
    text: string;
    sourceText: string;
    attachmentContent: JsonValue[];
    signature: string;
    textTooLong: boolean;
}

interface ParsedComposerDraft {
    text: string;
    sourceText: string;
    attachmentContent: JsonValue[];
    attachments: ChatAttachment[];
    soaiPathRecords: SoaiPathDraftRecord[];
    signature: string;
    revision: number;
}

interface ComposerDraftTransferTicket {
    complete(): Promise<void>;
    cancel(): void;
}

type ComposerDraftLoadSettlement = { status: 'ready'; draft: ParsedComposerDraft } | { status: 'failed'; error: Error };

export type { ComposerDraftApi, ComposerDraftLoadSettlement, ComposerDraftManagerDependencies, ComposerDraftProjection, ComposerDraftTransferTicket, ParsedComposerDraft };
