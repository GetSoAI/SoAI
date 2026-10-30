/* SoAI - Reusable attachment dialog consumer ports [frontend/assets/ts/features/attachmodal/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AttachmentAcquisitionScope } from '@core/attachments/protocols.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { AttachModalAction } from '@features/attachmodal/actions.ts';

type AttachModalTab = 'upload' | 'camera' | 'browse' | 'soaiLink' | 'knowledge';
const ATTACH_MODAL_TABS: readonly AttachModalTab[] = Object.freeze(['upload', 'camera', 'browse', 'soaiLink', 'knowledge']);
interface AttachModalOpenOptions {
    initialTab?: AttachModalTab;
}
interface AttachModalPolicy {
    readonly enabledTabs: readonly AttachModalTab[];
    readonly acceptedMedia: readonly ('image' | 'audio' | 'video' | 'document')[];
    readonly allowFolders: boolean;
}
interface AttachModalContent {
    activate(tab: AttachModalTab): void;
    deactivate(): void;
    handleAction(action: AttachModalAction, element: HTMLElement, event: Event): Promise<boolean>;
}
interface AttachModalSessionContext {
    readonly modal: HTMLElement;
    readonly signal: AbortSignal;
    isCurrent(): boolean;
    addCleanup(cleanup: () => void): void;
}
interface AttachModalConsumer {
    readonly policy: AttachModalPolicy;
    readonly presenter: ModalPresenterApi;
    signal(): AbortSignal | null;
    isAvailable(tab: AttachModalTab): boolean;
    disabledLabel(tab: AttachModalTab): string;
    counts(): Readonly<Record<AttachModalTab, number>>;
    subscribeChanges(handler: () => void): () => void;
    createContent(context: AttachModalSessionContext): AttachModalContent;
    captureCamera(): { scope: AttachmentAcquisitionScope; submit(file: File): Promise<void> };
    removeAll(tab: AttachModalTab): Promise<void>;
    run(operation: string, task: () => Promise<void> | void): void;
    reportCleanupFailure(error: Error): void;
}
interface AttachDraftListElements {
    status: HTMLElement;
    summary: HTMLElement;
    list: HTMLElement;
}
interface AttachUploadElements {
    dropzoneButton: HTMLButtonElement;
    filesButton: HTMLButtonElement;
    folderButton: HTMLButtonElement;
    draftList: AttachDraftListElements;
}
interface AttachLinkElements {
    input: HTMLTextAreaElement;
    error: HTMLElement;
    draftList: AttachDraftListElements;
}
interface AttachKnowledgeElements {
    documentInput: HTMLInputElement;
    folderInput: HTMLInputElement;
    dropzoneButton: HTMLButtonElement;
    documentsButton: HTMLButtonElement;
    folderButton: HTMLButtonElement;
    importButton: HTMLButtonElement;
    reindexButton: HTMLButtonElement;
    progress: HTMLElement;
    summary: HTMLElement;
    list: HTMLElement;
}
interface AttachBrowseElements {
    workspacePathInput: HTMLInputElement;
    workspacePathButton: HTMLButtonElement;
    searchInput: HTMLInputElement;
    results: HTMLElement;
    previewButton: HTMLButtonElement;
    attachButton: HTMLButtonElement;
    draftList: AttachDraftListElements;
}

export { ATTACH_MODAL_TABS };
export type { AttachBrowseElements, AttachDraftListElements, AttachKnowledgeElements, AttachLinkElements, AttachModalConsumer, AttachModalContent, AttachModalOpenOptions, AttachModalPolicy, AttachModalSessionContext, AttachModalTab, AttachUploadElements };
