/* SoAI - Shared UI session state [frontend/assets/ts/core/ui/modals/contentpreview/sessionState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeContentPreviewTextBaseline } from '@core/ui/modals/contentpreview/textBaseline.ts';
import type { ContentPreviewNonTextRequest, ContentPreviewOpenRequest, ContentPreviewTextSaveResult, ContentPreviewTextRequest } from '@core/ui/modals/contentpreview/types.ts';

type ContentPreviewClosedSessionState = Readonly<{
    mode: 'closed';
    request: null;
}>;

type ContentPreviewTextSessionMode = 'viewingText' | 'editingText' | 'busySave';

type ContentPreviewTextSessionState = Readonly<{
    mode: ContentPreviewTextSessionMode;
    request: ContentPreviewTextRequest;
}>;

type ContentPreviewMediaSessionState = Readonly<{
    mode: 'viewingMedia';
    request: ContentPreviewNonTextRequest;
}>;

type ContentPreviewSessionState = ContentPreviewClosedSessionState | ContentPreviewTextSessionState | ContentPreviewMediaSessionState;

const createClosedContentPreviewSessionState = (): ContentPreviewClosedSessionState =>
    Object.freeze({
        mode: 'closed',
        request: null
    });

const openContentPreviewSessionState = (request: ContentPreviewOpenRequest): ContentPreviewSessionState => {
    if (request.type === 'text') {
        return Object.freeze({
            mode: 'viewingText',
            request: Object.freeze({
                ...request,
                baseline: normalizeContentPreviewTextBaseline(request.baseline)
            })
        });
    }
    return Object.freeze({
        mode: 'viewingMedia',
        request
    });
};

const isContentPreviewTextSessionState = (state: ContentPreviewSessionState): state is ContentPreviewTextSessionState => state.request?.type === 'text';

const enterContentPreviewTextEditMode = (state: ContentPreviewSessionState): ContentPreviewSessionState => {
    if (!isContentPreviewTextSessionState(state)) {
        return state;
    }
    return Object.freeze({
        mode: 'editingText',
        request: state.request
    });
};

const exitContentPreviewTextEditMode = (state: ContentPreviewSessionState): ContentPreviewSessionState => {
    if (!isContentPreviewTextSessionState(state)) {
        return state;
    }
    return Object.freeze({
        mode: 'viewingText',
        request: state.request
    });
};

const beginContentPreviewTextSave = (state: ContentPreviewSessionState): ContentPreviewSessionState => {
    if (!isContentPreviewTextSessionState(state)) {
        return state;
    }
    return Object.freeze({
        mode: 'busySave',
        request: state.request
    });
};

const finishContentPreviewTextSave = (state: ContentPreviewSessionState, saveResult: ContentPreviewTextSaveResult | null): ContentPreviewSessionState => {
    if (!isContentPreviewTextSessionState(state)) {
        return state;
    }
    if (saveResult === null) {
        return Object.freeze({
            mode: 'editingText',
            request: state.request
        });
    }
    const openSourceUrl = saveResult.openSourceUrl !== undefined ? saveResult.openSourceUrl : state.request.openSourceUrl;
    const headerDescription = saveResult.headerDescription !== undefined ? saveResult.headerDescription : state.request.headerDescription;
    const nextRequest = Object.freeze({
        ...state.request,
        baseline: normalizeContentPreviewTextBaseline(saveResult.baseline),
        isUnsavedDraft: false,
        sourceReference: saveResult.sourceReference,
        headerDescription,
        openSourceUrl
    });
    return Object.freeze({
        mode: 'viewingText',
        request: nextRequest
    });
};

const closeContentPreviewSessionState = (): ContentPreviewClosedSessionState => createClosedContentPreviewSessionState();

export { beginContentPreviewTextSave, closeContentPreviewSessionState, createClosedContentPreviewSessionState, enterContentPreviewTextEditMode, exitContentPreviewTextEditMode, finishContentPreviewTextSave, isContentPreviewTextSessionState, openContentPreviewSessionState };
export type { ContentPreviewSessionState, ContentPreviewTextSessionState };
