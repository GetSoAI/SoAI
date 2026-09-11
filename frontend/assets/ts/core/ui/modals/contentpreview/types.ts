/* SoAI - Unified content preview modal request types [frontend/assets/ts/core/ui/modals/contentpreview/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export type ContentPreviewScope = 'prompts' | 'fileExplorer' | 'chat';
export type ContentPreviewType = 'text' | 'image' | 'audio' | 'video' | 'embed' | 'document' | 'file';

export type ContentPreviewTextLanguageMode = 'default' | 'plaintextIfSql';

export type ContentPreviewExternalOpenBehavior = 'auto' | 'alwaysConfirm' | 'neverConfirm';

export type ContentPreviewButtonLabels = Readonly<{
    close: string;
    cancel: string;
    download: string;
    copy: string;
    attach: string;
    openSource: string;
    edit: string;
    save: string;
    enhance: string;
    emptyCopyTitle: string;
    emptyDownloadTitle: string;
}>;

export type ContentPreviewTextBaseline = Readonly<{
    title: string;
    content: string;
    promptColor: string | null;
}>;

export type ContentPreviewTextDraftSnapshot = Readonly<{
    title: string;
    content: string;
    selectedColor: string | null;
}>;

export type ContentPreviewColorToolkitHooks = Readonly<{
    mountHeaderColorToolkit: (container: HTMLElement) => void;
    unmountHeaderColorToolkit: () => void;
}>;

export type ContentPreviewEnhanceAction = Readonly<{
    isEnabledForBaseline: (baseline: ContentPreviewTextBaseline) => boolean;
    disabledTitle: string | null;
    onRequestEnhance: () => Promise<void> | void;
}>;

export type ContentPreviewImageMetadata = Readonly<{
    contentType: string | null;
    contentLength: number | null;
}>;

export type ContentPreviewImageNavigation = Readonly<{
    position?: Readonly<{ current: number; total: number }>;
    previousLabel: string;
    nextLabel: string;
    previousLoadingPath: string;
    nextLoadingPath: string;
    onRequestPrevious: () => Promise<void> | void;
    onRequestNext: () => Promise<void> | void;
}>;

export type ContentPreviewImageNavigationDirection = 'previous' | 'next';

export type ContentPreviewPathSourceReference = Readonly<{
    type: 'path' | 'url';
    value: string;
}>;

export type ContentPreviewConversationSoaiPathSourceReference = Readonly<{
    type: 'conversation_soai_path';
    conversationId: string;
    rootFingerprint: string;
    value: string;
}>;

export type ContentPreviewSourceReference = ContentPreviewPathSourceReference | ContentPreviewConversationSoaiPathSourceReference;

export type ContentPreviewTextSaveResult = Readonly<{
    baseline: ContentPreviewTextBaseline;
    sourceReference: ContentPreviewSourceReference | null;
    headerDescription?: string | null;
    openSourceUrl?: string | null;
}>;

export type ContentPreviewTextRequest = Readonly<{
    scope: ContentPreviewScope;
    type: 'text';
    headerDescription: string | null;
    baseline: ContentPreviewTextBaseline;
    editable: boolean;
    isUnsavedDraft: boolean;
    languageMode: ContentPreviewTextLanguageMode;
    labels: ContentPreviewButtonLabels;
    disableCopyWhenEmpty: boolean;
    disableDownloadWhenEmpty: boolean;
    hideActionsWhenEmpty?: boolean | undefined;
    colorToolkit: ContentPreviewColorToolkitHooks | null;
    sourceReference: ContentPreviewSourceReference | null;
    onRequestSave: ((draft: ContentPreviewTextDraftSnapshot) => Promise<ContentPreviewTextSaveResult | null>) | null;
    onSaveComplete: (() => void) | null;
    onRequestDownload: (() => Promise<void> | void) | null;
    onRequestCopy: ((text: string) => Promise<void> | void) | null;
    onRequestAttach?: (() => Promise<void> | void) | null;
    enhance: ContentPreviewEnhanceAction | null;
    openSourceUrl: string | null;
    externalOpenBehavior: ContentPreviewExternalOpenBehavior;
    onStatePotentiallyChanged: (() => void) | null;
}>;

export type ContentPreviewMediaRequest = Readonly<{
    scope: ContentPreviewScope;
    type: Exclude<ContentPreviewType, 'text' | 'document' | 'file'>;
    headerDescription: string | null;
    title: string;
    sourceUrl: string;
    imageMetadata: ContentPreviewImageMetadata | null;
    imageNavigation?: ContentPreviewImageNavigation | null;
    sourceReference: ContentPreviewSourceReference | null;
    labels: ContentPreviewButtonLabels;
    onRequestDownload: (() => Promise<void> | void) | null;
    onRequestAttach?: (() => Promise<void> | void) | null;
    onSourceUrlRelease?: (() => void) | null;
    openSourceUrl: string | null;
    externalOpenBehavior: ContentPreviewExternalOpenBehavior;
}>;

export type ContentPreviewDocumentRequest = Readonly<{
    scope: ContentPreviewScope;
    type: 'document' | 'file';
    headerDescription: string | null;
    title: string;
    sourceReference: ContentPreviewSourceReference | null;
    labels: ContentPreviewButtonLabels;
    onRequestDownload: (() => Promise<void> | void) | null;
    onRequestAttach?: (() => Promise<void> | void) | null;
    openSourceUrl: string | null;
    externalOpenBehavior: ContentPreviewExternalOpenBehavior;
}>;

export type ContentPreviewNonTextRequest = ContentPreviewMediaRequest | ContentPreviewDocumentRequest;

export type ContentPreviewOpenRequest = ContentPreviewTextRequest | ContentPreviewMediaRequest | ContentPreviewDocumentRequest;
