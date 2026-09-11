/* SoAI - Shared UI modal wiring [frontend/assets/ts/core/ui/modals/contentpreview/modalWiring.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { isEditableKeyboardTarget } from '@core/dom/editableTargets.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { CONTENT_PREVIEW_ACTION_ATTR, CONTENT_PREVIEW_ACTIONS } from '@core/ui/modals/contentpreview/constants.ts';
import { i18n } from '@core/i18n/index.ts';
import { showNotification } from '@core/ui/notifications/notifications.ts';

type ContentPreviewAsyncAction = () => Promise<void> | void;

type ContentPreviewModalWiringArguments = Readonly<{
    resources: ResourceTracker;
    modalRoot: HTMLElement;
    handleClose: () => Promise<void>;
    handleDownload: () => Promise<void>;
    handleCopy: () => Promise<void>;
    handleAttach: () => Promise<void>;
    handleOpenSource: () => Promise<void>;
    enterEditMode: () => void;
    requestSave: () => Promise<void>;
    handleEnhance: () => Promise<void>;
    canNavigateImage: () => boolean;
    handleImagePrevious: () => Promise<void>;
    handleImageNext: () => Promise<void>;
    shouldHandleInput: () => boolean;
    handleInput: () => void;
}>;

const runContentPreviewAsyncAction = (actionName: string, action: ContentPreviewAsyncAction): void => {
    terminateHandledPromise(
        (async (): Promise<void> => {
            try {
                await action();
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.error('ContentPreviewModal', `Action failed: ${actionName}`, runtimeError);
                showNotification(i18n.t('contentPreview.errors.actionFailed'), 'error');
            }
        })()
    );
};

const isPlainImageNavigationKey = (event: KeyboardEvent): boolean => {
    return (event.key === 'ArrowLeft' || event.key === 'ArrowRight') && !event.altKey && !event.ctrlKey && !event.metaKey && !event.shiftKey;
};

const wireContentPreviewModalEvents = ({ resources, modalRoot, handleClose, handleDownload, handleCopy, handleAttach, handleOpenSource, enterEditMode, requestSave, handleEnhance, canNavigateImage, handleImagePrevious, handleImageNext, shouldHandleInput, handleInput }: ContentPreviewModalWiringArguments): void => {
    resources.addEventListener(modalRoot, 'click', (event: Event) => {
        if (event.defaultPrevented) {
            return;
        }
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }
        const actionElement = target.closest(`[${CONTENT_PREVIEW_ACTION_ATTR}]`);
        if (!(actionElement instanceof HTMLElement)) {
            return;
        }
        const action = actionElement.getAttribute(CONTENT_PREVIEW_ACTION_ATTR);
        if (!action) {
            return;
        }
        event.preventDefault();
        event.stopPropagation();

        if (action === CONTENT_PREVIEW_ACTIONS.CLOSE) {
            runContentPreviewAsyncAction(action, handleClose);
            return;
        }
        if (action === CONTENT_PREVIEW_ACTIONS.DOWNLOAD) {
            runContentPreviewAsyncAction(action, handleDownload);
            return;
        }
        if (action === CONTENT_PREVIEW_ACTIONS.COPY) {
            runContentPreviewAsyncAction(action, handleCopy);
            return;
        }
        if (action === CONTENT_PREVIEW_ACTIONS.ATTACH) {
            runContentPreviewAsyncAction(action, handleAttach);
            return;
        }
        if (action === CONTENT_PREVIEW_ACTIONS.OPEN_SOURCE) {
            runContentPreviewAsyncAction(action, handleOpenSource);
            return;
        }
        if (action === CONTENT_PREVIEW_ACTIONS.EDIT) {
            enterEditMode();
            return;
        }
        if (action === CONTENT_PREVIEW_ACTIONS.SAVE) {
            runContentPreviewAsyncAction(action, requestSave);
            return;
        }
        if (action === CONTENT_PREVIEW_ACTIONS.ENHANCE) {
            runContentPreviewAsyncAction(action, handleEnhance);
            return;
        }
        if (action === CONTENT_PREVIEW_ACTIONS.IMAGE_PREVIOUS) {
            runContentPreviewAsyncAction(action, handleImagePrevious);
            return;
        }
        if (action === CONTENT_PREVIEW_ACTIONS.IMAGE_NEXT) {
            runContentPreviewAsyncAction(action, handleImageNext);
            return;
        }

        throw new Error(`Unhandled content preview action: "${action}"`);
    });

    resources.addEventListener(
        modalRoot.ownerDocument,
        'keydown',
        (event: Event) => {
            if (!(event instanceof KeyboardEvent)) {
                return;
            }
            if (event.defaultPrevented || event.isComposing) {
                return;
            }
            if (isPlainImageNavigationKey(event) && canNavigateImage() && !isEditableKeyboardTarget(event.target)) {
                event.preventDefault();
                event.stopPropagation();
                runContentPreviewAsyncAction(event.key, event.key === 'ArrowLeft' ? handleImagePrevious : handleImageNext);
                return;
            }
        },
        { capture: true }
    );

    resources.addEventListener(modalRoot, 'keydown', (event: Event) => {
        if (!(event instanceof KeyboardEvent)) {
            return;
        }
        if (event.defaultPrevented || event.isComposing) {
            return;
        }
        if (event.key !== 'Enter' || (!event.ctrlKey && !event.metaKey)) {
            return;
        }
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }
        if (!target.matches('.prompt-modal-content-textarea, .prompt-modal-title-input')) {
            return;
        }
        event.preventDefault();
        event.stopPropagation();
        runContentPreviewAsyncAction('keyboardSave', requestSave);
    });

    resources.addEventListener(modalRoot, 'input', () => {
        if (!shouldHandleInput()) {
            return;
        }
        handleInput();
    });
};

export { wireContentPreviewModalEvents, runContentPreviewAsyncAction };
