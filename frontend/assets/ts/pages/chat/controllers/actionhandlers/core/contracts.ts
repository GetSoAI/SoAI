/* SoAI - Chat action routing domain contracts [frontend/assets/ts/pages/chat/controllers/actionhandlers/core/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SecretPromptInteractionResolutionRequest } from '@core/api/contracts/webuiChatOperationContracts.ts';
import type { KnowledgeAttachmentSummary } from '@core/api/contracts/webuiAttachmentContracts.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { ChatActionId, ChatAttachment, ChatPageApi, ChatStreamStopOptions, ChatTurnAdmissionSnapshot, ComposerDraftTransferMode, Conversation, ConversationContract, ConversationWorkspacePathConfig, RagIngestionAttachmentSource, RagIngestionStatus, SoaiPathDraftRecord } from '@features/chat/public.ts';
import type { ConversationInputComposerOutcome, SendMessageOptions } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';
import type { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageFeedback } from '@core/routing/pages/basepagecore/PageFeedback.ts';

type ChatActionHandler = (actionElement: HTMLElement, event: Event) => void;

interface ChatConversationActionsControllerContract {
    createConversation(options?: { transferMode?: ComposerDraftTransferMode }): Promise<Conversation | null>;
    ensureConversationPersisted(conversation: ConversationContract): Promise<void>;
    handleNewConversationClick(actionElement?: HTMLElement | null): void;
    collapseSidebarIfNarrowViewport(): void;
    deleteConversationById(conversationId: string): void;
    archiveConversationById(conversationId: string): void;
    openConversationEnsuringLoaded(conversationId: string): void;
    toggleConversationFavoriteById(conversationId: string, actionElement?: HTMLElement | null): void;
    switchConversationById(conversationId: string): void;
    startConversationRenameById(conversationId: string): Promise<void>;
    startCurrentConversationTitleEdit(): Promise<void>;
    handleConversationTitleSave(): Promise<void>;
    handleConversationTitleCancel(): void;
    handleConversationListTitleSave(): Promise<void>;
    handleConversationListTitleCancel(): void;
    updateConversationColorById(conversationId: string, color: string | null): void;
}

interface ChatSharedActionPort {
    pageResources: PageResources;
    feedback: PageFeedback;
    api: ChatPageApi;
}

interface ChatNavigationActionPort {
    navigate(page: string): void;
    navigateWithQuery(page: string, query: Record<string, string>): void;
}

interface ChatConversationActionPort {
    actions: ChatConversationActionsControllerContract;
    currentModel(): string | null;
    current(): Conversation | null;
    currentId(): string | null;
    export(conversationId: string | null): void;
    updateWorkspacePath(conversationId: string, config: ConversationWorkspacePathConfig): void;
    isStreaming(conversationId: string): boolean;
    isExecuting(conversationId: string): boolean;
    requireId(actionElement: HTMLElement, ancestorSelector: string | null): string;
    openEnsuringLoaded(conversationId: string): void;
    refreshSidebar(): Promise<void>;
}

interface ChatExecutionActionPort {
    canQueue(conversationId: string): boolean;
    admission(conversationId: string): ChatTurnAdmissionSnapshot;
    syncAdmission(conversationId: string): Promise<ChatTurnAdmissionSnapshot>;
    stop(options?: ChatStreamStopOptions): void;
    run(operationId: string, task: () => Promise<void> | void): void;
    boundary<T>(name: string, functionValue: () => Promise<T>): Promise<T>;
    send(options?: SendMessageOptions): Promise<void>;
    steer(): Promise<ConversationInputComposerOutcome>;
    queue(intent: 'queued' | 'steer'): Promise<ConversationInputComposerOutcome>;
}

interface ChatComposerActionPort {
    cycleTokenCounter(): void;
    requireInput(): HTMLTextAreaElement;
    setInput(input: HTMLTextAreaElement, value: string): void;
    cancelConversationInput(conversationId: string, inputId: string): Promise<void>;
    retryConversationRegeneration(conversationId: string, inputId: string): Promise<void>;
    resolveAskUser(conversationId: string, taskId: string, action: 'submit' | 'cancel'): Promise<void>;
    resolveSecret(conversationId: string, taskId: string, request: SecretPromptInteractionResolutionRequest): Promise<void>;
    resolveToolApproval(conversationId: string, taskId: string, action: 'approve' | 'deny'): Promise<void>;
    toggleCall(): void;
    toggleTools(): Promise<void>;
    openCharacterMap(): void;
    updateInputState(): void;
    applyInputActionVisibility(): void;
    updateInputQueuePreview(): void;
    resolvePrimaryActionMode(): import('@features/chat/public.ts').ChatComposerActionMode;
}

interface ChatAttachDraftCounts {
    upload: number;
    camera: number;
    browse: number;
    soaiLink: number;
    knowledge: number;
}

type ChatAttachDraftRemovalSource = keyof ChatAttachDraftCounts;

interface ChatAttachmentActionPort {
    fileUploadEnabled(): boolean;
    cameraEnabled(): boolean;
    drafts(): readonly ChatAttachment[];
    draftCounts(): ChatAttachDraftCounts;
    draftCommitEpoch(): number;
    subscribeDrafts(handler: () => void): () => void;
    requireFileInput(): HTMLInputElement;
    requireFolderInput(): HTMLInputElement;
    uploadFiles(files: File[]): Promise<void>;
    uploadFolder(files: File[]): Promise<void>;
    captureCamera(file: File): Promise<void>;
    addSoaiPaths(records: readonly SoaiPathDraftRecord[], source: 'browse' | 'soaiLink'): number;
    removeFile(fileId: string): Promise<void>;
    removeKnowledge(knowledgeAttachmentId: string): Promise<void>;
    removeAll(source: ChatAttachDraftRemovalSource): Promise<void>;
}

interface ChatAudioActionPort {
    toggleRecording(): void;
    cancelRecording(): void;
}

interface ChatConfigurationActionPort {
    toggle(): void;
    openTab(tabId: string): void;
    openMemoryProfile(): void;
    refreshMemory(): Promise<void>;
    handleModelAction(actionElement: HTMLElement): void;
    refreshPresets(): void;
    resetPresets(): void;
    newPreset(): void;
    applyPreset(actionElement: HTMLElement): void;
    replacePreset(actionElement: HTMLElement): void;
    renamePreset(actionElement: HTMLElement): void;
    removePreset(actionElement: HTMLElement): void;
    submitPresetEditor(): void;
    cancelPresetEditor(): void;
    reviewPresetEditor(): void;
    restoreDefaults(): Promise<void> | void;
    save(): void;
    openToolOutput(inputArguments: { conversationId: string; callId: string; assistantTurnTimestamp: number; modelVariantIndex: number }): Promise<void>;
}

interface ChatPresentationActionPort {
    toggleFavoritesAtTop(): void;
    toggleSidebar(): void;
    actionData(actionElement: HTMLElement, key: string): string | null;
    showColorPicker(actionElement: HTMLElement, conversationId: string): void;
    activeColorPickerConversationId(): string | null;
    hideColorPicker(): void;
    hasClipboardSupport(): boolean;
    copyToClipboard(text: string, options?: { notify?: (message: string, type: NotificationType) => void }): Promise<void>;
    copyCodeBlock(actionElement: HTMLElement): Promise<void>;
    copyInlineMediaReference(actionElement: HTMLElement): Promise<void>;
    openInlineMediaLocalFolder(actionElement: HTMLElement): Promise<void>;
    dispatchMessageAction(actionElement: HTMLElement, action: ChatActionId, event: Event): void;
    handleComparisonNavigation(actionElement: HTMLElement): void;
    handleModelControlAction(actionElement: HTMLElement): void;
    uploadAssistantAvatar(): void;
    removeAssistantAvatar(): void;
    uploadUserAvatar(): void;
    removeUserAvatar(): void;
    toggleToolActivityItem(actionElement: HTMLElement): void;
}

interface ChatAgentActionPort {
    cycleMode(): void;
    compact(): void;
    toggleTodoPanel(): void;
    togglePlanBar(): void;
    viewPlan(): void;
    executePlan(): Promise<void>;
}

interface ChatToolbarActionPort {
    toggle(): void;
    enterSelectMode(): void;
    exitSelectMode(): void;
    deleteSelected(): Promise<void>;
    cloneSelected(): Promise<void>;
    archiveSelected(): Promise<void>;
    openArchived(): void;
    openPrompts(): void;
    selectionActive(): boolean;
    toggleSelection(conversationId: string): void;
}

interface ChatRagActionPort {
    cancel(): Promise<void>;
    status(conversationId: string): RagIngestionStatus | null;
    subscribe(handler: () => void): () => void;
    start(inputArguments: { conversationId: string; conversation: Conversation; files: File[]; attachmentSource: RagIngestionAttachmentSource }): Promise<void>;
    handleKnowledgeChanged(summary: KnowledgeAttachmentSummary): void;
    cancelForConversation(conversationId: string): Promise<void>;
}

interface ChatActionHandlersHost {
    shared: ChatSharedActionPort;
    navigation: ChatNavigationActionPort;
    conversation: ChatConversationActionPort;
    execution: ChatExecutionActionPort;
    composer: ChatComposerActionPort;
    attachments: ChatAttachmentActionPort;
    audio: ChatAudioActionPort;
    configuration: ChatConfigurationActionPort;
    presentation: ChatPresentationActionPort;
    agent: ChatAgentActionPort;
    toolbar: ChatToolbarActionPort;
    rag: ChatRagActionPort;
}

export type { ChatActionHandler, ChatActionHandlersHost, ChatAgentActionPort, ChatAttachDraftCounts, ChatAttachDraftRemovalSource, ChatAttachmentActionPort, ChatAudioActionPort, ChatComposerActionPort, ChatConfigurationActionPort, ChatConversationActionPort, ChatConversationActionsControllerContract, ChatExecutionActionPort, ChatNavigationActionPort, ChatPresentationActionPort, ChatRagActionPort, ChatSharedActionPort, ChatToolbarActionPort };
