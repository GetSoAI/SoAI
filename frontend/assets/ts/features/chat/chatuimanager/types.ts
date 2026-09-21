/* SoAI - Chat UI manager contracts [frontend/assets/ts/features/chat/chatuimanager/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import type { ConversationInputState } from '@core/api/contracts/chatQueueDraftContracts.ts';
import type { KnowledgeAttachmentSummary } from '@core/api/contracts/webuiAttachmentContracts.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { SanitizerApi } from '@core/pagecontext/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { ChatAttachment, ChatContentSegment, ChatMessage, ConversationContract, ToolActivityItem } from '@features/chat/ChatTypes.ts';
import type { InlineActivityDetailsCancelRequest, InlineActivityDetailsRenderRequest } from '@features/chat/message/inlineActivityDetailsIdentity.ts';
import type { MessageReferenceResolver } from '@features/chat/message/messageReferenceResolution.ts';
import type { RagIngestionStatus } from '@features/chat/ingestion/types.ts';
import type { ChatTurnAdmissionSnapshot } from '@features/chat/chatstreamservice/types.ts';
import type { MessageCursor } from '@features/chat/storage/storageModels.ts';
import type { MessageWindowScrollAnchor } from '@features/chat/chatuimanager/messageWindowScrollAnchor.ts';

type DebouncedHandler = {
    (): void;
    cancel?: () => void;
};

export type ConversationInputPreview = {
    inputId: string;
    inputType: 'prompt' | 'steer';
    state: ConversationInputState | 'regeneration_failed';
    text: string;
    attachmentContent: readonly ChatContentSegment[];
};

type MessageWindowRequestDirection = 'before' | 'after';

export type AdvancedScrollPreviewElements = {
    messagesArea: HTMLElement;
    messagesRoot: HTMLElement;
    overlay: HTMLElement;
    canvas: HTMLElement;
    viewport: HTMLElement;
    fadeTop: HTMLElement;
    fadeBottom: HTMLElement;
};

export type AdvancedScrollPreviewVisibilityController = {
    sync: (visibleWanted: boolean) => void;
    suspend: () => void;
    resume: () => void;
    isVisible: () => boolean;
    dispose: () => void;
};

export type ChatComposerActionMode = 'send' | 'stop' | 'steer' | 'queue';

export type ElementSelectorKey = 'input' | 'actionBtn' | 'attachBtn' | 'messagesArea' | 'preview' | 'inputQueuePreview' | 'toolApprovalPreview' | 'askUserPreview' | 'secretPromptPreview' | 'voiceRecordingPreview';

interface ChatUiCompositionPort {
    applyTextZoom: () => void;
    updateExportButtonVisibility: () => void;
    applyWidescreenMode: () => void;
    applySidebarState: () => void;
}

interface ChatUiSidebarPort {
    getSidebarOpen: () => boolean;
    setSidebarOpen: (open: boolean) => void;
    persistSidebarOpen: (open: boolean) => void;
}

interface ChatUiSessionPort {
    getCurrentConversationId: () => string | null;
    getCurrentConversation: () => ConversationContract | null;
    getCurrentModel: () => string | null;
    getModelStreamHasPayload: () => boolean;
    isModelAvailable: (modelId: string) => boolean;
    isConversationExecuting: (conversationId: string) => boolean;
    getTurnAdmission: (conversationId: string) => ChatTurnAdmissionSnapshot;
    hasActiveComparisonRun: (conversationId: string) => boolean;
    isThinkingFeatureEnabled: () => boolean;
    hasPendingAttachmentProcessing: () => boolean;
}

interface ChatUiDraftPort {
    getAttachments: () => ChatAttachment[] | null;
    getRagIngestionStatus: () => RagIngestionStatus | null;
    getDraftKnowledgeAttachments: () => readonly KnowledgeAttachmentSummary[] | null;
    refreshDraftKnowledgeAttachments: () => void;
    cancelRagIngestion: () => Promise<void>;
    getConversationInputs: () => ConversationInputPreview[] | null;
    saveChatState: (force?: boolean) => void;
    requestMessageWindow: (direction: MessageWindowRequestDirection) => void;
}

interface ChatUiRuntimePort {
    on: (target: EventTarget, event: string, handler: (event: Event) => void, options?: AddEventListenerOptions) => () => void;
    createDebouncedHandler: <TArguments extends (JsonValue | null | undefined)[]>(functionValue: (...inputArguments: TArguments) => void, delay: number) => ((...inputArguments: TArguments) => void) & { cancel?: () => void };
    setTimer: (functionValue: () => void, delay: number) => number;
    clearTimer: (timer: number) => void;
}

interface ChatUiDomPort {
    getDocument: () => Document;
    getData: (element: Element | null, key: string) => string | null;
    setHTML: (element: Element, html: TrustedHtml | string, options?: { escape?: boolean }) => void;
    setStyle: (element: HTMLElement, prop: string, value: string | null) => void;
}

interface ChatUiMessagePort {
    resolveMessageReference: MessageReferenceResolver;
    renderInlineActivityDetailsAsync: (inputArguments: InlineActivityDetailsRenderRequest) => void;
    cancelInlineActivityDetailsRender: (inputArguments: InlineActivityDetailsCancelRequest) => void;
    postRender: (container: Element | null) => void;
    invalidateMessageCache: (message: ChatMessage) => void;
    invalidateMessageProjectionCache: (message: ChatMessage) => void;
}

export interface ChatUiManagerDependencies {
    sanitizer: SanitizerApi;
    optionalUI: (selector: string, context?: Element) => Element | null;
    queryUI: (selector: string, context?: Element) => Element[];
    toggleClassName: (element: Element, className: string, add: boolean) => void;
    updateAttribute: (element: Element, attr: string, value: string | null) => void;
    updateProperty: (element: Element, prop: string, value: DomPropertyValue) => void;
    updateHTML: (element: Element, html: TrustedHtml | string) => void;
    getCachedIcon: (name: IconName, options?: IconOptions) => TrustedHtml;
    dom: ChatUiDomPort;
    composition: ChatUiCompositionPort;
    sidebar: ChatUiSidebarPort;
    session: ChatUiSessionPort;
    drafts: ChatUiDraftPort;
    runtime: ChatUiRuntimePort;

    messageManager: ChatUiMessagePort;
    hydrateToolImageProjection: (inputArguments: { conversationId: string; callId: string; assistantTurnAtMs: number; modelVariantIndex: number }) => Promise<ToolActivityItem | null>;
}

export interface ChatUIManagerState {
    autoScrollEnabled: boolean;
    autoScrollUserIntentActive: boolean;
    autoScrollIntentDisposers: Array<() => void>;
    elementCache: Partial<Record<ElementSelectorKey, HTMLElement | null>>;
    scrollTimer: number | null;
    olderMessagesRequestTimer: number | null;
    scrollDebounceHandler: DebouncedHandler | null;
    scrollListenerDisposer: (() => void) | null;
    scrollListenerMessagesArea: HTMLElement | null;
    messagesAutoScrollLockDisposer: (() => void) | null;
    messagesAutoScrollLockArea: HTMLElement | null;
    conversationScrollSnapshotByConversationId: Map<string, { cursor: MessageCursor; renderAnchor: MessageWindowScrollAnchor }>;
    pendingConversationScrollRestoreConversationId: string | null;
    activeConversationScrollRestore: { conversationId: string; generation: number; messagesArea: HTMLElement; renderAnchor: MessageWindowScrollAnchor; disposers: Array<() => void>; settleTimer: number | null; completion: (cancelled: boolean) => void } | null;
    conversationScrollRestoreGeneration: number;
    attachedFilesPreviewLayoutDisposer: (() => void) | null;
    advancedScrollPreviewDisposer: (() => void) | null;
    advancedScrollPreviewOverlay: HTMLElement | null;
    advancedScrollPreviewVisibilityController: AdvancedScrollPreviewVisibilityController | null;
    activeConversationTransitionId: number | null;
    messagesAreaInsetsDisposer: (() => void) | null;
    modalPresenter: ModalPresenterApi | null;
}

export interface ChatUIManagerContext {
    dependencies: ChatUiManagerDependencies;
    elementSelectors: Record<ElementSelectorKey, string>;
    state: ChatUIManagerState;
}

export type { MessageWindowRequestDirection };
