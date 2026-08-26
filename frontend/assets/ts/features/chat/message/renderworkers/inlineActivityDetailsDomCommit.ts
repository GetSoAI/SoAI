/* SoAI - Chat feature inline activity details DOM commit [frontend/assets/ts/features/chat/message/renderworkers/inlineActivityDetailsDomCommit.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { parseSingleRootElement } from '@core/dom/parseSingleRootElement.ts';
import { i18n } from '@core/i18n/index.ts';
import { collectAssistantDomState } from '@features/chat/message/assistantDomState.ts';
import { patchStreamingTimelineSegmentInPlace } from '@features/chat/message/assistantTimelineSegmentPatching.ts';
import { patchInlineActivityDetailsContent } from '@features/chat/message/assistantToolDetailsPatching.ts';
import { withAssistantViewportStability } from '@features/chat/message/assistantViewportStability.ts';
import { inlineActivityDetailsSignatureIsCurrent, readInlineActivityDetailsSignature, syncInlineActivityDetailsRootSignature } from '@features/chat/message/inlineActivityDetailsLifecycle.ts';
import { INLINE_ACTIVITY_DETAILS_SIGNATURE_ATTRIBUTE, resolveDirectInlineActivityDetailsRoot } from '@features/chat/message/inlineActivityDetailsIdentity.ts';
import { completeInlineActivityDetailsOpenState } from '@features/chat/message/inlineActivityDetailsPendingState.ts';

interface InlineActivityDetailsSuccessCommitRequest {
    item: HTMLElement;
    signature: string;
    html: string;
    postRenderEffects: (container: Element | null) => void;
}

interface InlineActivityDetailsFailureCommitRequest {
    item: HTMLElement;
    signature: string;
}

const createInlineActivityDetailsRoot = (item: HTMLElement, signature: string, html: string): HTMLElement => {
    const created = html ? parseSingleRootElement({ documentRef: item.ownerDocument, html: toTrustedUiHtml(html), context: item }) : null;
    if (!(created instanceof HTMLElement) || !created.classList.contains('inline-activity-details')) {
        throw new Error('Chat worker returned invalid inline activity details markup');
    }
    created.setAttribute(INLINE_ACTIVITY_DETAILS_SIGNATURE_ATTRIBUTE, signature);
    return created;
};

const inlineActivityDetailsAlreadyCurrent = (item: HTMLElement, detailsRoot: HTMLElement, signature: string): boolean => {
    return readInlineActivityDetailsSignature(item) === signature && inlineActivityDetailsSignatureIsCurrent(item, detailsRoot);
};

const commitInlineActivityDetailsRenderSuccess = (request: InlineActivityDetailsSuccessCommitRequest): void => {
    const existingDetailsRoot = resolveDirectInlineActivityDetailsRoot(request.item);
    if (existingDetailsRoot instanceof HTMLElement && inlineActivityDetailsAlreadyCurrent(request.item, existingDetailsRoot, request.signature)) {
        withAssistantViewportStability(request.item, () => {
            completeInlineActivityDetailsOpenState(request.item);
        });
        request.postRenderEffects(existingDetailsRoot);
        return;
    }
    let committedDetailsRoot: HTMLElement | null = null;
    const created = createInlineActivityDetailsRoot(request.item, request.signature, request.html.trim());
    withAssistantViewportStability(request.item, () => {
        if (existingDetailsRoot instanceof HTMLElement) {
            syncInlineActivityDetailsRootSignature(request.item, existingDetailsRoot, request.signature);
            const assistantDomState = collectAssistantDomState(existingDetailsRoot);
            patchInlineActivityDetailsContent(existingDetailsRoot, created, patchStreamingTimelineSegmentInPlace, { assistantDomState }, false);
            committedDetailsRoot = existingDetailsRoot;
        } else {
            request.item.appendChild(created);
            committedDetailsRoot = created;
        }
        completeInlineActivityDetailsOpenState(request.item);
    });
    request.postRenderEffects(committedDetailsRoot);
};

const commitInlineActivityDetailsRenderFailure = (request: InlineActivityDetailsFailureCommitRequest): void => {
    withAssistantViewportStability(request.item, () => {
        let detailsRoot = resolveDirectInlineActivityDetailsRoot(request.item);
        if (!(detailsRoot instanceof HTMLElement)) {
            detailsRoot = request.item.ownerDocument.createElement('div');
            detailsRoot.className = 'inline-activity-details';
            detailsRoot.setAttribute(INLINE_ACTIVITY_DETAILS_SIGNATURE_ATTRIBUTE, request.signature);
            request.item.appendChild(detailsRoot);
        }
        detailsRoot.textContent = '';
        detailsRoot.appendChild(detailsRoot.ownerDocument.createTextNode(i18n.t('chat.message.renderFailed')));
        completeInlineActivityDetailsOpenState(request.item);
    });
};

export { commitInlineActivityDetailsRenderFailure, commitInlineActivityDetailsRenderSuccess };
