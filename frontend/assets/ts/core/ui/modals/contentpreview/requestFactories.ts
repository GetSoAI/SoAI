/* SoAI - Shared UI request factories [frontend/assets/ts/core/ui/modals/contentpreview/requestFactories.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveContentPreviewButtonLabels } from '@core/ui/modals/contentpreview/labels.ts';
import { resolveContentPreviewExternalOpenBehavior } from '@core/ui/modals/contentpreview/scopeDefaults.ts';
import { normalizeContentPreviewSourceReference, resolveContentPreviewDisplayTitle } from '@core/ui/modals/contentpreview/sourceReference.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ContentPreviewButtonLabels, ContentPreviewDocumentRequest, ContentPreviewExternalOpenBehavior, ContentPreviewMediaRequest, ContentPreviewScope, ContentPreviewSourceReference, ContentPreviewTextBaseline, ContentPreviewTextRequest } from '@core/ui/modals/contentpreview/types.ts';

type ContentPreviewRequestDefaultsArguments = Readonly<{
    scope: ContentPreviewScope;
    externalOpenBehavior?: ContentPreviewExternalOpenBehavior | null;
    sourceReference?: ContentPreviewSourceReference | null;
}>;

type ContentPreviewTextRequestFactoryArguments = Omit<ContentPreviewTextRequest, 'labels' | 'externalOpenBehavior' | 'sourceReference' | 'onSaveComplete' | 'isUnsavedDraft'> &
    ContentPreviewRequestDefaultsArguments & {
        onSaveComplete?: (() => void) | null;
        isUnsavedDraft?: boolean;
    };
type ContentPreviewMediaRequestFactoryArguments = Omit<ContentPreviewMediaRequest, 'labels' | 'externalOpenBehavior' | 'sourceReference'> & ContentPreviewRequestDefaultsArguments;
type ContentPreviewDocumentRequestFactoryArguments = Omit<ContentPreviewDocumentRequest, 'labels' | 'externalOpenBehavior' | 'sourceReference'> & ContentPreviewRequestDefaultsArguments;

const resolveExternalOpenBehavior = (inputArguments: ContentPreviewRequestDefaultsArguments): ContentPreviewExternalOpenBehavior => {
    if (inputArguments.externalOpenBehavior) {
        return inputArguments.externalOpenBehavior;
    }
    return resolveContentPreviewExternalOpenBehavior(inputArguments.scope);
};

const resolveTextBaseline = (baseline: ContentPreviewTextBaseline, sourceReference: ContentPreviewSourceReference | null): ContentPreviewTextBaseline =>
    Object.freeze({
        ...baseline,
        title: resolveContentPreviewDisplayTitle(baseline.title, sourceReference)
    });

const resolveLabels = (scope: ContentPreviewScope, sourceReference: ContentPreviewSourceReference | null): ContentPreviewButtonLabels => {
    const labels = resolveContentPreviewButtonLabels(scope);
    if (!sourceReference) {
        return labels;
    }
    return Object.freeze({
        ...labels,
        openSource: sourceReference.type === 'url' ? i18n.t('contentPreview.actions.goToUrl') : i18n.t('contentPreview.actions.goToPath')
    });
};

const createTextContentPreviewRequest = (inputArguments: ContentPreviewTextRequestFactoryArguments): ContentPreviewTextRequest => {
    const sourceReference = normalizeContentPreviewSourceReference(inputArguments.sourceReference);
    return Object.freeze({
        ...inputArguments,
        baseline: resolveTextBaseline(inputArguments.baseline, sourceReference),
        sourceReference,
        onSaveComplete: inputArguments.onSaveComplete ?? null,
        onRequestAttach: inputArguments.onRequestAttach ?? null,
        isUnsavedDraft: inputArguments.isUnsavedDraft === true,
        hideActionsWhenEmpty: inputArguments.hideActionsWhenEmpty === true,
        labels: resolveLabels(inputArguments.scope, sourceReference),
        externalOpenBehavior: resolveExternalOpenBehavior(inputArguments)
    });
};

const createMediaContentPreviewRequest = (inputArguments: ContentPreviewMediaRequestFactoryArguments): ContentPreviewMediaRequest => {
    const sourceReference = normalizeContentPreviewSourceReference(inputArguments.sourceReference);
    return Object.freeze({
        ...inputArguments,
        title: resolveContentPreviewDisplayTitle(inputArguments.title, sourceReference),
        sourceReference,
        onRequestAttach: inputArguments.onRequestAttach ?? null,
        labels: resolveLabels(inputArguments.scope, sourceReference),
        externalOpenBehavior: resolveExternalOpenBehavior(inputArguments)
    });
};

const createDocumentContentPreviewRequest = (inputArguments: ContentPreviewDocumentRequestFactoryArguments): ContentPreviewDocumentRequest => {
    const sourceReference = normalizeContentPreviewSourceReference(inputArguments.sourceReference);
    return Object.freeze({
        ...inputArguments,
        title: resolveContentPreviewDisplayTitle(inputArguments.title, sourceReference),
        sourceReference,
        onRequestAttach: inputArguments.onRequestAttach ?? null,
        labels: resolveLabels(inputArguments.scope, sourceReference),
        externalOpenBehavior: resolveExternalOpenBehavior(inputArguments)
    });
};

export { createDocumentContentPreviewRequest, createMediaContentPreviewRequest, createTextContentPreviewRequest };
