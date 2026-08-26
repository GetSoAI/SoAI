/* SoAI - Shared UI modal runtime [frontend/assets/ts/core/ui/modals/contentpreview/modalRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { setModalHeaderDescription } from '@core/modals/headerDescription.ts';
import { requireModalPresenter, type ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { createSaveController, SAVE_HEADER_PRIORITY_MODAL, type SaveController } from '@core/save/public.ts';
import { applyButtonLabels, applyEditingUiState, applyTextEmptyDisableState } from '@core/ui/modals/contentpreview/modalButtons.ts';
import { CONTENT_PREVIEW_MODAL_ID } from '@core/ui/modals/contentpreview/constants.ts';
import { requireContentPreviewHeaderColorContainer, requireContentPreviewSaveButton } from '@core/ui/modals/contentpreview/dom.ts';
import { createContentPreviewMediaController } from '@core/ui/modals/contentpreview/mediaController.ts';
import { requestContentPreviewTextSave } from '@core/ui/modals/contentpreview/saveFlow.ts';
import { normalizeContentPreviewOpenRequest } from '@core/ui/modals/contentpreview/requestValidation.ts';
import { closeContentPreviewSessionState, createClosedContentPreviewSessionState, enterContentPreviewTextEditMode, exitContentPreviewTextEditMode, isContentPreviewTextSessionState, openContentPreviewSessionState, type ContentPreviewSessionState } from '@core/ui/modals/contentpreview/sessionState.ts';
import { clearContentPreviewHeaderColorToolkit, renderContentPreviewMediaMode, renderContentPreviewTextMode } from '@core/ui/modals/contentpreview/sessionRendering.ts';
import { wireContentPreviewModalEvents } from '@core/ui/modals/contentpreview/modalWiring.ts';
import { createContentPreviewRuntimeActions } from '@core/ui/modals/contentpreview/runtimeActions.ts';
import { createContentPreviewTextController } from '@core/ui/modals/contentpreview/textController.ts';
import type { ContentPreviewImageNavigation, ContentPreviewImageNavigationDirection, ContentPreviewMediaRequest, ContentPreviewOpenRequest, ContentPreviewTextRequest } from '@core/ui/modals/contentpreview/types.ts';
import type { ContentPreviewServiceApi } from '@core/ui/modals/contentpreview/serviceApi.ts';
import { attachBeforeCloseConfirmationGuard } from '@core/modals/closeGuard.ts';
import { showUnsavedChangesConfirmation } from '@core/modals/unsavedChangesConfirmation.ts';

export const createContentPreviewModalRuntime = (): ContentPreviewServiceApi => {
    const resources = new ResourceTracker();
    const modalPresenter: ModalPresenterApi = requireModalPresenter();

    const textController = createContentPreviewTextController(resources);
    const mediaController = createContentPreviewMediaController(resources);
    const sessionRenderingDependencies = {
        resetMedia: (root: HTMLElement): void => mediaController.reset(root),
        resetText: (root: HTMLElement): void => textController.reset(root),
        renderTextViewMode: (root: HTMLElement, request: ContentPreviewTextRequest): void => textController.renderViewMode(root, request),
        renderMedia: (root: HTMLElement, request: Exclude<ContentPreviewOpenRequest, ContentPreviewTextRequest>): void => mediaController.render(root, request)
    };

    let wired = false;
    let sessionState: ContentPreviewSessionState = createClosedContentPreviewSessionState();
    let saveController: SaveController | null = null;

    const requireModalRoot = (): HTMLElement => modalPresenter.requireElement(CONTENT_PREVIEW_MODAL_ID);

    const applyHeaderDescription = (modalRoot: HTMLElement, text: string | null): void => {
        setModalHeaderDescription(modalRoot, modalUiId(CONTENT_PREVIEW_MODAL_ID, 'description'), text);
    };

    const getCurrentRequest = (): ContentPreviewOpenRequest | null => sessionState.request;

    const getCurrentTextRequest = (): ContentPreviewTextRequest | null => {
        if (!isContentPreviewTextSessionState(sessionState)) {
            return null;
        }
        return sessionState.request;
    };

    const getCurrentImageNavigation = (): ContentPreviewImageNavigation | null => {
        const request = getCurrentRequest();
        if (!request || request.type !== 'image') {
            return null;
        }
        return request.imageNavigation ?? null;
    };

    const notifyPotentialChange = (): void => {
        const request = getCurrentTextRequest();
        if (!request) {
            return;
        }
        saveController?.notifyChanged();
        request.onStatePotentiallyChanged?.();
    };

    const enterEditMode = (): void => {
        const request = getCurrentTextRequest();
        if (!request) {
            return;
        }
        if (!request.editable) {
            return;
        }
        if (textController.isEditing()) {
            return;
        }
        const modalRoot = requireModalRoot();
        request.colorToolkit?.mountHeaderColorToolkit(requireContentPreviewHeaderColorContainer(modalRoot));
        textController.enterEditMode(modalRoot, request);
        sessionState = enterContentPreviewTextEditMode(sessionState);
        applyEditingUiState(modalRoot, request, true);
        notifyPotentialChange();
    };

    const exitEditMode = (): void => {
        const request = getCurrentTextRequest();
        if (!request) {
            return;
        }
        if (!textController.isEditing()) {
            return;
        }
        const modalRoot = requireModalRoot();
        textController.exitEditMode(modalRoot, request);
        clearContentPreviewHeaderColorToolkit(modalRoot, request);
        sessionState = exitContentPreviewTextEditMode(sessionState);
        applyEditingUiState(modalRoot, request, false);
        applyTextEmptyDisableState(modalRoot, request);
        notifyPotentialChange();
    };

    const confirmDraftDiscard = async (): Promise<boolean> => {
        if (saveController?.isSaving()) {
            return false;
        }
        if (!textController.hasDraftChanges()) {
            return true;
        }
        return await showUnsavedChangesConfirmation();
    };

    const handleClose = async (): Promise<void> => {
        if (textController.isEditing()) {
            if (!(await confirmDraftDiscard())) {
                return;
            }
            const discardsWholeSession = getCurrentTextRequest()?.isUnsavedDraft === true;
            exitEditMode();
            if (!discardsWholeSession) {
                return;
            }
        }
        modalPresenter.close(CONTENT_PREVIEW_MODAL_ID, { reason: 'trigger' });
    };

    const requestTextSave = async (): Promise<void> => {
        const request = getCurrentTextRequest();
        if (!request) {
            return;
        }
        const modalRoot = requireModalRoot();
        await requestContentPreviewTextSave({
            modalRoot,
            request,
            textController,
            getCurrentTextRequest,
            getSessionState: (): ContentPreviewSessionState => sessionState,
            setSessionState: (state: ContentPreviewSessionState): void => {
                sessionState = state;
            },
            notifyPotentialChange
        });
    };

    const actions = createContentPreviewRuntimeActions({
        getCurrentRequest,
        getCurrentTextRequest,
        getCurrentImageNavigation,
        beginImageNavigation: (direction: ContentPreviewImageNavigationDirection, loadingLabel: string): void => mediaController.beginImageNavigation(direction, loadingLabel),
        cancelImageNavigation: (): void => mediaController.cancelImageNavigation(),
        requireModalRoot,
        textController
    });

    const wireOnce = (modalRoot: HTMLElement): void => {
        if (wired) {
            return;
        }
        wired = true;

        wireContentPreviewModalEvents({
            resources,
            modalRoot,
            handleClose,
            handleDownload: actions.handleDownload,
            handleCopy: actions.handleCopy,
            handleAttach: actions.handleAttach,
            handleOpenSource: actions.handleOpenSource,
            enterEditMode,
            requestSave: requestTextSave,
            handleEnhance: actions.handleEnhance,
            canNavigateImage: (): boolean => modalPresenter.isOpen(CONTENT_PREVIEW_MODAL_ID) && getCurrentImageNavigation() !== null && !mediaController.isImageNavigationPending(),
            handleImagePrevious: actions.handleImagePrevious,
            handleImageNext: actions.handleImageNext,
            shouldHandleInput: (): boolean => {
                const request = getCurrentTextRequest();
                if (!request) {
                    return false;
                }
                return textController.isEditing() && sessionState.mode !== 'busySave';
            },
            handleInput: (): void => {
                textController.getDraftSnapshot(modalRoot);
                notifyPotentialChange();
            }
        });

        resources.addEventListener(modalRoot, 'core.modal.close', () => {
            const request = getCurrentRequest();
            sessionState = closeContentPreviewSessionState();
            mediaController.dispose();
            textController.reset(modalRoot);
            clearContentPreviewHeaderColorToolkit(modalRoot, request);
            applyHeaderDescription(modalRoot, null);
            saveController?.notifyChanged();
        });

        saveController = createSaveController({
            headerContextId: CONTENT_PREVIEW_MODAL_ID,
            headerPriority: SAVE_HEADER_PRIORITY_MODAL,
            requestContextLabel: 'Content preview save',
            units: [
                {
                    id: 'content-preview-text',
                    hasChanges: (): boolean => getCurrentTextRequest() !== null && textController.hasDraftChanges(),
                    isValid: (): boolean => {
                        const request = getCurrentTextRequest();
                        return Boolean(request?.editable && request.onRequestSave);
                    },
                    save: async (): Promise<void> => {
                        await requestTextSave();
                    }
                }
            ]
        });
        saveController.attach({
            resolveSaveButtons: (): readonly HTMLButtonElement[] => [requireContentPreviewSaveButton(modalRoot)],
            autoNotifyRoot: modalRoot
        });
        resources.track(
            attachBeforeCloseConfirmationGuard({
                modal: modalRoot,
                presenter: modalPresenter,
                modalId: CONTENT_PREVIEW_MODAL_ID,
                shouldConfirmClose: (): boolean => textController.hasDraftChanges() || saveController?.isSaving() === true,
                confirmClose: confirmDraftDiscard
            })
        );
    };

    const open = (request: ContentPreviewOpenRequest): void => {
        const normalizedRequest = normalizeContentPreviewOpenRequest(request);
        const modalRoot = requireModalRoot();
        wireOnce(modalRoot);
        const previousRequest = getCurrentRequest();
        sessionState = openContentPreviewSessionState(normalizedRequest);
        if (normalizedRequest.type === 'text') {
            renderContentPreviewTextMode(sessionRenderingDependencies, modalRoot, normalizedRequest, previousRequest);
        } else {
            renderContentPreviewMediaMode(sessionRenderingDependencies, modalRoot, normalizedRequest, previousRequest);
        }
        applyHeaderDescription(modalRoot, normalizedRequest.headerDescription);

        modalPresenter.open(CONTENT_PREVIEW_MODAL_ID);
        saveController?.notifyChanged();
    };

    return {
        open,
        completeImageNavigation: async (request: ContentPreviewMediaRequest, direction: ContentPreviewImageNavigationDirection): Promise<boolean> => {
            const normalizedRequest = normalizeContentPreviewOpenRequest(request);
            if (normalizedRequest.type !== 'image') {
                throw new Error('Image navigation completion requires an image request');
            }
            const modalRoot = requireModalRoot();
            const committed = await mediaController.completeImageNavigation(modalRoot, normalizedRequest, direction);
            if (!committed) {
                return false;
            }
            sessionState = openContentPreviewSessionState(normalizedRequest);
            applyButtonLabels(modalRoot, normalizedRequest.labels);
            applyEditingUiState(modalRoot, normalizedRequest, false);
            applyHeaderDescription(modalRoot, normalizedRequest.headerDescription);
            saveController?.notifyChanged();
            return true;
        },
        close: (): void => modalPresenter.close(CONTENT_PREVIEW_MODAL_ID, { reason: 'trigger' }),
        isOpen: (): boolean => modalPresenter.isOpen(CONTENT_PREVIEW_MODAL_ID),
        isEditing: (): boolean => textController.isEditing(),
        enterEditMode,
        exitEditMode,
        hasTextDraftChanges: (): boolean => textController.hasDraftChanges(),
        getTextDraftSnapshot: (): ReturnType<ContentPreviewServiceApi['getTextDraftSnapshot']> => {
            const request = getCurrentTextRequest();
            if (!request) {
                return null;
            }
            const modalRoot = requireModalRoot();
            return textController.getDraftSnapshot(modalRoot);
        },
        requestSave: requestTextSave,
        setTextSelectedColor: (color: string | null): void => {
            const request = getCurrentTextRequest();
            if (!request) {
                return;
            }
            const modalRoot = requireModalRoot();
            textController.setSelectedColor(modalRoot, color);
            notifyPotentialChange();
        }
    };
};
