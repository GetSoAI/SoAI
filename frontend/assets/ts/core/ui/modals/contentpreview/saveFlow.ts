/* SoAI - Content preview text save flow [frontend/assets/ts/core/ui/modals/contentpreview/saveFlow.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { setModalHeaderDescription } from '@core/modals/headerDescription.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { applyBusyState, applyEditingUiState, applyTextEmptyDisableState } from '@core/ui/modals/contentpreview/modalButtons.ts';
import { CONTENT_PREVIEW_MODAL_ID } from '@core/ui/modals/contentpreview/constants.ts';
import { beginContentPreviewTextSave, finishContentPreviewTextSave, type ContentPreviewSessionState } from '@core/ui/modals/contentpreview/sessionState.ts';
import { clearContentPreviewHeaderColorToolkit } from '@core/ui/modals/contentpreview/sessionRendering.ts';
import { normalizeContentPreviewSourceReference, resolveContentPreviewDisplayTitle } from '@core/ui/modals/contentpreview/sourceReference.ts';
import type { ContentPreviewTextController } from '@core/ui/modals/contentpreview/textController.ts';
import type { ContentPreviewTextRequest, ContentPreviewTextSaveResult } from '@core/ui/modals/contentpreview/types.ts';

type ContentPreviewTextSaveFlowArguments = Readonly<{
    modalRoot: HTMLElement;
    request: ContentPreviewTextRequest;
    textController: ContentPreviewTextController;
    getCurrentTextRequest: () => ContentPreviewTextRequest | null;
    getSessionState: () => ContentPreviewSessionState;
    setSessionState: (state: ContentPreviewSessionState) => void;
    notifyPotentialChange: () => void;
}>;

const normalizeSaveResult = (saveResult: ContentPreviewTextSaveResult): ContentPreviewTextSaveResult => {
    const sourceReference = normalizeContentPreviewSourceReference(saveResult.sourceReference);
    const normalizedBase = {
        baseline: Object.freeze({
            ...saveResult.baseline,
            title: resolveContentPreviewDisplayTitle(saveResult.baseline.title, sourceReference)
        }),
        sourceReference
    };
    const normalized = saveResult.headerDescription !== undefined ? { ...normalizedBase, headerDescription: saveResult.headerDescription } : normalizedBase;
    if (saveResult.openSourceUrl !== undefined) {
        return Object.freeze({
            ...normalized,
            openSourceUrl: saveResult.openSourceUrl
        });
    }
    return Object.freeze(normalized);
};

const requestContentPreviewTextSave = async ({ modalRoot, request, textController, getCurrentTextRequest, getSessionState, setSessionState, notifyPotentialChange }: ContentPreviewTextSaveFlowArguments): Promise<void> => {
    if (!textController.isEditing() || !request.editable || !request.onRequestSave) {
        return;
    }

    const draft = textController.getDraftSnapshot(modalRoot);
    if (!draft) {
        throw new Error('Content preview draft snapshot is missing');
    }

    setSessionState(beginContentPreviewTextSave(getSessionState()));
    applyBusyState(modalRoot, true);
    let busyCleared = false;
    try {
        const saveResult = await request.onRequestSave(draft);
        if (getCurrentTextRequest() !== request) {
            return;
        }
        if (!saveResult) {
            return;
        }
        const normalizedResult = normalizeSaveResult(saveResult);
        const committedRequest = Object.freeze({
            ...request,
            sourceReference: normalizedResult.sourceReference
        });
        const normalizedBaseline = textController.applySavedBaseline(modalRoot, committedRequest, normalizedResult.baseline);
        const finalizedResultCore = {
            baseline: normalizedBaseline,
            sourceReference: normalizedResult.sourceReference
        };
        const finalizedResultBase = normalizedResult.headerDescription !== undefined ? { ...finalizedResultCore, headerDescription: normalizedResult.headerDescription } : finalizedResultCore;
        const finalizedResult = Object.freeze(
            normalizedResult.openSourceUrl !== undefined
                ? {
                      ...finalizedResultBase,
                      openSourceUrl: normalizedResult.openSourceUrl
                  }
                : finalizedResultBase
        );
        setSessionState(finishContentPreviewTextSave(getSessionState(), finalizedResult));
        setModalHeaderDescription(modalRoot, modalUiId(CONTENT_PREVIEW_MODAL_ID, 'description'), normalizedResult.headerDescription ?? request.headerDescription);
        applyBusyState(modalRoot, false);
        busyCleared = true;
        const nextRequest = getCurrentTextRequest();
        if (!nextRequest) {
            throw new Error('Content preview saved text request is missing');
        }
        clearContentPreviewHeaderColorToolkit(modalRoot, nextRequest);
        applyEditingUiState(modalRoot, nextRequest, false);
        applyTextEmptyDisableState(modalRoot, nextRequest);
        notifyPotentialChange();
        request.onSaveComplete?.();
    } finally {
        if (!busyCleared && getCurrentTextRequest() === request) {
            setSessionState(finishContentPreviewTextSave(getSessionState(), null));
            applyBusyState(modalRoot, false);
        }
    }
};

export { requestContentPreviewTextSave };
