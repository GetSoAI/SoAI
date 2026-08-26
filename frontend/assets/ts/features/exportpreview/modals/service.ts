/* SoAI - Shared export preview modal service [frontend/assets/ts/features/exportpreview/modals/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { decodeExportPreviewSnapshot } from '@core/api/contracts/exportPreviewContracts.ts';
import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';
import { shouldPreventDefaultForActionElement } from '@core/dom/dataAction.ts';
import { bindDataActionListener } from '@core/dom/dataActionBinding.ts';
import { getDocument } from '@core/environment/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { triggerDownloadLink } from '@core/primitives/download.ts';
import { requireSyntaxHighlighter } from '@core/syntaxhighlighter/public.ts';
import { isHTMLElement, isNode } from '@core/typeGuards.ts';
import { requestWebSocketSnapshot } from '@core/websocketclient/service.ts';
import { EXPORT_PREVIEW_ACTION_DOWNLOAD, EXPORT_PREVIEW_MODAL_ID } from '@features/exportpreview/modals/constants.ts';
import { requireContentElement, requireTitleElement, setDownloadDisabled, setLoadingVisible } from '@features/exportpreview/modals/dom.ts';
import { createExportPreviewModalState } from '@features/exportpreview/modals/state.ts';
import type { ExportPreviewModalDependencies, ExportPreviewModalEventBinding, ExportPreviewModalHost, ExportPreviewModalOpenRequest, ExportPreviewModalState, ExportPreviewSnapshotPayload } from '@features/exportpreview/modals/types.ts';

const { guard: isExportPreviewActionId } = createActionIdSet(EXPORT_PREVIEW_ACTION_DOWNLOAD);
const EXPORT_PREVIEW_DOWNLOAD_BOUNDARY = 'exportPreview:download';

class ExportPreviewModal {
    readonly modalId = EXPORT_PREVIEW_MODAL_ID;
    readonly host: ExportPreviewModalHost;
    readonly #openToken = new SequenceToken();
    #state: ExportPreviewModalState;
    #snapshotAbortController: AbortController | null = null;

    constructor({ host }: ExportPreviewModalDependencies) {
        if (!host) {
            throw new Error('ExportPreviewModal requires a host');
        }
        this.host = host;
        this.#state = createExportPreviewModalState();
    }

    bindModalEvents({ modalRoot, signal }: ExportPreviewModalEventBinding): void {
        const documentRef = getDocument();
        documentRef.addEventListener(
            'core.modal.close',
            (event: Event): void => {
                const target = event.target;
                if (isHTMLElement(target) && target.id === this.modalId) {
                    this.handleModalClosed();
                }
            },
            { signal }
        );
        bindDataActionListener({
            root: modalRoot,
            eventType: 'click',
            signal,
            isAction: isExportPreviewActionId,
            mouseButton: 'primary',
            preventDefault: 'never',
            onAction: ({ event, action, actionElement }): void | Promise<void> => {
                if (action !== EXPORT_PREVIEW_ACTION_DOWNLOAD) {
                    return;
                }
                if (shouldPreventDefaultForActionElement(actionElement)) {
                    event.preventDefault();
                }
                return this.download();
            }
        });
    }

    handleModalClosed(): void {
        this.#openToken.invalidate();
        this.#abortSnapshot();
        this.#state = createExportPreviewModalState();
    }

    disposeForPageLifecycle(reason: string): void {
        this.#openToken.invalidate();
        this.#abortSnapshot();
        this.#state = createExportPreviewModalState();
        if (this.host.modals.isOpen(this.modalId)) {
            this.host.modals.close(this.modalId, { force: true, restoreFocus: false, reason });
        }
    }

    async open(request: ExportPreviewModalOpenRequest): Promise<void> {
        return this.host.runWithBoundary(request.boundaryName, async () => {
            const modalRoot = this.host.modals.requireElement(this.modalId);
            const openToken = this.#openToken.next();
            this.#abortSnapshot();
            const abortController = new AbortController();
            this.#snapshotAbortController = abortController;
            this.#state = {
                isOpen: true,
                scope: request.scope,
                filename: '',
                content: '',
                downloadUrl: '',
                downloadBoundaryName: request.downloadBoundaryName
            };
            modalRoot.setAttribute('data-page-scope', request.scope);

            const titleElement = requireTitleElement(this.host, modalRoot);
            const contentElement = requireContentElement(this.host, modalRoot);
            this.host.updateText(titleElement, i18n.t('common.exportPreview.title'));
            contentElement.textContent = '';
            setLoadingVisible(this.host, modalRoot, true);
            setDownloadDisabled(this.host, modalRoot, true);
            this.host.modals.open(this.modalId);

            try {
                const payload = await this.#loadPayload(request, abortController.signal);
                if (!this.#openToken.isActive(openToken)) {
                    return;
                }
                this.#renderPayload(modalRoot, titleElement, contentElement, payload);
            } catch (error) {
                if (!this.#openToken.isActive(openToken)) {
                    return;
                }
                this.#state = createExportPreviewModalState();
                setLoadingVisible(this.host, modalRoot, false);
                setDownloadDisabled(this.host, modalRoot, true);
                throw error;
            } finally {
                if (this.#snapshotAbortController === abortController) {
                    this.#snapshotAbortController = null;
                }
            }
        });
    }

    async download(): Promise<void> {
        const boundaryName = this.#state.downloadBoundaryName || EXPORT_PREVIEW_DOWNLOAD_BOUNDARY;
        return this.host.runWithBoundary(boundaryName, async () => {
            const previewDownloadUrl = this.#state.downloadUrl;
            if (!previewDownloadUrl) {
                throw new Error('Export preview download requested before preview is ready');
            }
            triggerDownloadLink({ href: previewDownloadUrl, forceDownload: true });
            this.host.showNotification(i18n.t('common.notifications.downloadStarted'), 'download');
        });
    }

    async #loadPayload(request: ExportPreviewModalOpenRequest, signal: AbortSignal): Promise<ExportPreviewSnapshotPayload> {
        const snapshot = await requestWebSocketSnapshot(request.snapshotResource, request.payload, { signal });
        if (snapshot.resource !== request.snapshotResource) {
            throw new Error(`WebSocket snapshot envelope is invalid for ${request.snapshotResource}`);
        }
        return decodeExportPreviewSnapshot(snapshot.data, `${request.snapshotResource} snapshot`);
    }

    #renderPayload(modalRoot: HTMLElement, titleElement: HTMLElement, contentElement: HTMLElement, payload: ExportPreviewSnapshotPayload): void {
        this.host.updateText(titleElement, payload.filename);
        contentElement.textContent = '';
        const finalPreview = payload.previewTruncated ? `${payload.previewText}\n\n${i18n.t('common.exportPreview.previewTruncated')}` : payload.previewText;
        const highlighter = requireSyntaxHighlighter();
        const highlighted = highlighter.highlight(finalPreview, 'plaintext');
        if (isNode(highlighted)) {
            contentElement.appendChild(highlighted);
        } else {
            const pre = getDocument().createElement('pre');
            pre.textContent = String(highlighted);
            contentElement.appendChild(pre);
        }
        this.#state.filename = payload.filename;
        this.#state.downloadUrl = payload.downloadUrl;
        this.#state.content = finalPreview;
        setLoadingVisible(this.host, modalRoot, false);
        setDownloadDisabled(this.host, modalRoot, false);
    }

    #abortSnapshot(): void {
        const controller = this.#snapshotAbortController;
        this.#snapshotAbortController = null;
        if (controller) {
            controller.abort();
        }
    }
}

export { ExportPreviewModal };
