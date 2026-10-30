/* SoAI - Chat attach modal element resolution [frontend/assets/ts/features/attachmodal/elements.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ATTACH_MODAL_ID } from '@features/attachmodal/constants.ts';
import type { AttachCameraElements } from '@features/attachmodal/cameraCapture.ts';

import type { AttachBrowseElements, AttachDraftListElements, AttachKnowledgeElements, AttachLinkElements, AttachUploadElements } from '@features/attachmodal/contracts.ts';
import { dom } from '@core/dom/dom.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';

const requireAttachModalChild = (modal: HTMLElement, token: string): HTMLElement => {
    const element = dom.resolve(modalUiSelector(ATTACH_MODAL_ID, token), modal);
    if (!(element instanceof HTMLElement)) {
        throw new Error(`Chat attach modal requires "${token}" element`);
    }
    return element;
};

const requireAttachModalButton = (modal: HTMLElement, token: string): HTMLButtonElement => {
    const element = requireAttachModalChild(modal, token);
    if (!(element instanceof HTMLButtonElement)) {
        throw new Error(`Chat attach modal "${token}" control must be a button`);
    }
    return element;
};

const requireAttachModalVideo = (modal: HTMLElement, token: string): HTMLVideoElement => {
    const element = requireAttachModalChild(modal, token);
    if (!(element instanceof HTMLVideoElement)) {
        throw new Error(`Chat attach modal "${token}" control must be a video element`);
    }
    return element;
};

const requireAttachModalCanvas = (modal: HTMLElement, token: string): HTMLCanvasElement => {
    const element = requireAttachModalChild(modal, token);
    if (!(element instanceof HTMLCanvasElement)) {
        throw new Error(`Chat attach modal "${token}" control must be a canvas element`);
    }
    return element;
};

const requireAttachModalInput = (modal: HTMLElement, token: string): HTMLInputElement => {
    const element = requireAttachModalChild(modal, token);
    if (!(element instanceof HTMLInputElement)) {
        throw new Error(`Chat attach modal "${token}" control must be an input element`);
    }
    return element;
};

const requireAttachModalTextarea = (modal: HTMLElement, token: string): HTMLTextAreaElement => {
    const element = requireAttachModalChild(modal, token);
    if (!(element instanceof HTMLTextAreaElement)) {
        throw new Error(`Chat attach modal "${token}" control must be a textarea element`);
    }
    return element;
};

const createAttachCameraElements = (modal: HTMLElement): AttachCameraElements => ({
    pane: requireAttachModalChild(modal, 'pane-camera'),
    stage: requireAttachModalChild(modal, 'camera-stage'),
    video: requireAttachModalVideo(modal, 'camera-video'),
    canvas: requireAttachModalCanvas(modal, 'camera-canvas'),
    status: requireAttachModalChild(modal, 'camera-status'),
    shutterButton: requireAttachModalButton(modal, 'camera-shutter'),
    retakeButton: requireAttachModalButton(modal, 'camera-retake'),
    useButton: requireAttachModalButton(modal, 'camera-use'),
    switchButton: requireAttachModalButton(modal, 'camera-switch')
});

const createAttachBrowseElements = (modal: HTMLElement): AttachBrowseElements => ({
    workspacePathInput: requireAttachModalInput(modal, 'browse-workspace-path'),
    workspacePathButton: requireAttachModalButton(modal, 'browse-workspace-change-btn'),
    searchInput: requireAttachModalInput(modal, 'search'),
    results: requireAttachModalChild(modal, 'results'),
    previewButton: requireAttachModalButton(modal, 'browse-preview'),
    attachButton: requireAttachModalButton(modal, 'browse-attach'),
    draftList: createAttachDraftListElements(modal, 'browse')
});

const createAttachDraftListElements = (modal: HTMLElement, tokenPrefix: 'upload' | 'camera' | 'browse' | 'soai-link'): AttachDraftListElements => ({
    status: requireAttachModalChild(modal, `${tokenPrefix}-status`),
    summary: requireAttachModalChild(modal, `${tokenPrefix}-summary`),
    list: requireAttachModalChild(modal, `${tokenPrefix}-list`)
});

const createAttachUploadElements = (modal: HTMLElement): AttachUploadElements => ({
    dropzoneButton: requireAttachModalButton(modal, 'dropzone'),
    filesButton: requireAttachModalButton(modal, 'upload-file-button'),
    folderButton: requireAttachModalButton(modal, 'upload-folder-button'),
    draftList: createAttachDraftListElements(modal, 'upload')
});

const createAttachLinkElements = (modal: HTMLElement): AttachLinkElements => ({
    input: requireAttachModalTextarea(modal, 'soai-link-input'),
    error: requireAttachModalChild(modal, 'soai-link-error'),
    draftList: createAttachDraftListElements(modal, 'soai-link')
});

const createAttachKnowledgeElements = (modal: HTMLElement): AttachKnowledgeElements => ({
    documentInput: requireAttachModalInput(modal, 'knowledge-document-input'),
    folderInput: requireAttachModalInput(modal, 'knowledge-folder-input'),
    dropzoneButton: requireAttachModalButton(modal, 'knowledge-dropzone'),
    documentsButton: requireAttachModalButton(modal, 'knowledge-file-button'),
    folderButton: requireAttachModalButton(modal, 'knowledge-folder-button'),
    importButton: requireAttachModalButton(modal, 'knowledge-import'),
    reindexButton: requireAttachModalButton(modal, 'knowledge-reindex'),
    progress: requireAttachModalChild(modal, 'knowledge-progress'),
    summary: requireAttachModalChild(modal, 'knowledge-summary'),
    list: requireAttachModalChild(modal, 'knowledge-documents-list')
});

export { createAttachBrowseElements, createAttachCameraElements, createAttachDraftListElements, createAttachKnowledgeElements, createAttachLinkElements, createAttachUploadElements, requireAttachModalButton, requireAttachModalChild };
