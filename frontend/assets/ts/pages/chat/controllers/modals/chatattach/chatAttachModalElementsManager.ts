/* SoAI - Chat attach modal element resolution [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachModalElementsManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { CHAT_ATTACH_MODAL_ID, type ChatAttachCameraElements } from '@features/chat/public.ts';
import type { ChatAttachBrowseElements } from '@pages/chat/controllers/modals/chatattach/chatAttachBrowseWidget.ts';
import type { ChatAttachDraftAttachmentListElements, ChatAttachKnowledgeElements, ChatAttachSoaiLinkElements, ChatAttachUploadElements } from '@pages/chat/controllers/modals/chatattach/types.ts';

const requireChatAttachModalChild = (modal: HTMLElement, token: string): HTMLElement => {
    const element = dom.resolve(modalUiSelector(CHAT_ATTACH_MODAL_ID, token), modal);
    if (!(element instanceof HTMLElement)) {
        throw new Error(`Chat attach modal requires "${token}" element`);
    }
    return element;
};

const requireChatAttachModalButton = (modal: HTMLElement, token: string): HTMLButtonElement => {
    const element = requireChatAttachModalChild(modal, token);
    if (!(element instanceof HTMLButtonElement)) {
        throw new Error(`Chat attach modal "${token}" control must be a button`);
    }
    return element;
};

const requireChatAttachModalVideo = (modal: HTMLElement, token: string): HTMLVideoElement => {
    const element = requireChatAttachModalChild(modal, token);
    if (!(element instanceof HTMLVideoElement)) {
        throw new Error(`Chat attach modal "${token}" control must be a video element`);
    }
    return element;
};

const requireChatAttachModalCanvas = (modal: HTMLElement, token: string): HTMLCanvasElement => {
    const element = requireChatAttachModalChild(modal, token);
    if (!(element instanceof HTMLCanvasElement)) {
        throw new Error(`Chat attach modal "${token}" control must be a canvas element`);
    }
    return element;
};

const requireChatAttachModalInput = (modal: HTMLElement, token: string): HTMLInputElement => {
    const element = requireChatAttachModalChild(modal, token);
    if (!(element instanceof HTMLInputElement)) {
        throw new Error(`Chat attach modal "${token}" control must be an input element`);
    }
    return element;
};

const requireChatAttachModalTextarea = (modal: HTMLElement, token: string): HTMLTextAreaElement => {
    const element = requireChatAttachModalChild(modal, token);
    if (!(element instanceof HTMLTextAreaElement)) {
        throw new Error(`Chat attach modal "${token}" control must be a textarea element`);
    }
    return element;
};

const createChatAttachCameraElements = (modal: HTMLElement): ChatAttachCameraElements => ({
    pane: requireChatAttachModalChild(modal, 'pane-camera'),
    stage: requireChatAttachModalChild(modal, 'camera-stage'),
    video: requireChatAttachModalVideo(modal, 'camera-video'),
    canvas: requireChatAttachModalCanvas(modal, 'camera-canvas'),
    status: requireChatAttachModalChild(modal, 'camera-status'),
    shutterButton: requireChatAttachModalButton(modal, 'camera-shutter'),
    retakeButton: requireChatAttachModalButton(modal, 'camera-retake'),
    useButton: requireChatAttachModalButton(modal, 'camera-use'),
    switchButton: requireChatAttachModalButton(modal, 'camera-switch')
});

const createChatAttachBrowseElements = (modal: HTMLElement): ChatAttachBrowseElements => ({
    workspacePathInput: requireChatAttachModalInput(modal, 'browse-workspace-path'),
    workspacePathButton: requireChatAttachModalButton(modal, 'browse-workspace-change-btn'),
    searchInput: requireChatAttachModalInput(modal, 'search'),
    results: requireChatAttachModalChild(modal, 'results'),
    previewButton: requireChatAttachModalButton(modal, 'browse-preview'),
    attachButton: requireChatAttachModalButton(modal, 'browse-attach'),
    draftList: createChatAttachDraftListElements(modal, 'browse')
});

const createChatAttachDraftListElements = (modal: HTMLElement, tokenPrefix: 'upload' | 'camera' | 'browse' | 'soai-link'): ChatAttachDraftAttachmentListElements => ({
    status: requireChatAttachModalChild(modal, `${tokenPrefix}-status`),
    summary: requireChatAttachModalChild(modal, `${tokenPrefix}-summary`),
    list: requireChatAttachModalChild(modal, `${tokenPrefix}-list`)
});

const createChatAttachUploadElements = (modal: HTMLElement): ChatAttachUploadElements => ({
    dropzoneButton: requireChatAttachModalButton(modal, 'dropzone'),
    filesButton: requireChatAttachModalButton(modal, 'upload-file-button'),
    folderButton: requireChatAttachModalButton(modal, 'upload-folder-button'),
    draftList: createChatAttachDraftListElements(modal, 'upload')
});

const createChatAttachSoaiLinkElements = (modal: HTMLElement): ChatAttachSoaiLinkElements => ({
    input: requireChatAttachModalTextarea(modal, 'soai-link-input'),
    draftList: createChatAttachDraftListElements(modal, 'soai-link')
});

const createChatAttachKnowledgeElements = (modal: HTMLElement): ChatAttachKnowledgeElements => ({
    documentInput: requireChatAttachModalInput(modal, 'knowledge-document-input'),
    folderInput: requireChatAttachModalInput(modal, 'knowledge-folder-input'),
    dropzoneButton: requireChatAttachModalButton(modal, 'knowledge-dropzone'),
    documentsButton: requireChatAttachModalButton(modal, 'knowledge-file-button'),
    folderButton: requireChatAttachModalButton(modal, 'knowledge-folder-button'),
    importButton: requireChatAttachModalButton(modal, 'knowledge-import'),
    reindexButton: requireChatAttachModalButton(modal, 'knowledge-reindex'),
    progress: requireChatAttachModalChild(modal, 'knowledge-progress'),
    summary: requireChatAttachModalChild(modal, 'knowledge-summary'),
    list: requireChatAttachModalChild(modal, 'knowledge-documents-list')
});

export { createChatAttachBrowseElements, createChatAttachCameraElements, createChatAttachDraftListElements, createChatAttachKnowledgeElements, createChatAttachSoaiLinkElements, createChatAttachUploadElements, requireChatAttachModalButton, requireChatAttachModalChild };
