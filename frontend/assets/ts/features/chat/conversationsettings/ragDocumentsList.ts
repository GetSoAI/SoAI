/* SoAI - Chat feature RAG documents list [frontend/assets/ts/features/chat/conversationsettings/ragDocumentsList.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import { checkerboardService, type ElementOptions } from '@core/dom/dom.ts';
import { resolveFileEntryIconName } from '@core/fileexplorerbrowser/entryIconResolution.ts';
import { replaceChildrenFromTrustedHtml } from '@core/dom/html.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import { normalizeProgressParts, normalizeProgressPercent } from '@core/primitives/progress.ts';
import { isNumber, isString } from '@core/typeGuards.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { syncDeterminateProgress } from '@core/ui/progressWidths.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { sanitizeTitle } from '@features/chat/conversationFormatting.ts';
import { isRagDocumentProcessingStatus } from '@features/chat/conversationsettings/ragDocumentStatus.ts';
import type { RagDocument } from '@features/chat/conversationsettings/settingsModels.ts';

interface DomService {
    getDocument(): Document;
    setStyle(element: HTMLElement, prop: string, value: string | null): void;
}

interface ConversationSettingsUiHost {
    dom: DomService;
    createElement(tag: string, options?: ElementOptions, content?: string | Node): HTMLElement;
    updateHTML(element: Element, html: string): void;
    updateText(element: Element, text: string): void;
    updateProperty(element: Element, prop: string, value: DomPropertyValue): void;
    updateAttribute(element: Element, attr: string, value: string | null): void;
    toggleClassName(element: Element, className: string, add: boolean): void;
    appendToElement(parent: Element, child: Node | Node[]): void;
}

interface RagStatusInfo {
    label: string;
    className: string;
}

interface RenderRagDocumentsDependencies {
    host: ConversationSettingsUiHost;
    container: Element;
    emptyState: Element | null;
    documents: RagDocument[];
    count: number;
    limit: number;
    offset: number;
    ragDocumentProgress: Map<string, number>;
    resolveRagStatus: (document: RagDocument) => RagStatusInfo;
}

const setRagDocumentProgressStyle = (host: ConversationSettingsUiHost, element: Element, property: string, value: string): void => {
    if (!(element instanceof HTMLElement)) {
        throw new TypeError('RAG progress bar must be an HTML element');
    }
    host.dom.setStyle(element, property, value);
};

const syncRagDocumentProgress = (host: ConversationSettingsUiHost, progressBar: Element, progressContainer: Element, percent: number): void => {
    syncDeterminateProgress({
        fillElement: progressBar,
        progress: percent,
        progressbarElement: progressContainer,
        setStyle: (element, property, value): void => setRagDocumentProgressStyle(host, element, property, value),
        setAttribute: (element, name, value): void => host.updateAttribute(element, name, value)
    });
};

const renderRagDocumentsList = ({ host, container, emptyState, documents, count, limit, offset, ragDocumentProgress, resolveRagStatus }: RenderRagDocumentsDependencies): void => {
    host.updateHTML(container, '');
    if (documents.length === 0) {
        checkerboardService.applyCheckerboard(container, '.rag-document-item', offset);
        if (emptyState !== null) {
            host.updateText(emptyState, i18n.t('chat.configuration.rag.documentsEmpty'));
            host.toggleClassName(emptyState, 'u-hidden', false);
        }
        return;
    }
    if (emptyState !== null) {
        host.toggleClassName(emptyState, 'u-hidden', true);
    }

    const documentRef = host.dom.getDocument();
    const fragment = documentRef.createDocumentFragment();
    documents.forEach((item) => {
        const row = host.createElement('div', { class: 'rag-document-item' });
        const leadingIcon = host.createElement('span', { class: 'file-preview-leading-icon rag-document-leading-icon', 'aria-hidden': 'true' });
        replaceChildrenFromTrustedHtml({ element: leadingIcon, html: getIconSync(resolveFileEntryIconName({ name: item.filename, isDirectory: false }), { size: 20, strokeWidth: 1.5 }), context: leadingIcon });
        const info = host.createElement('div', { class: 'rag-document-info' });
        const header = host.createElement('div', { class: 'rag-document-header' });
        const name = host.createElement('div', { class: 'rag-document-name' });
        host.updateText(name, sanitizeTitle(item.filename));
        const statusInfo = resolveRagStatus(item);
        const badge = host.createElement('span', { class: `ui-status-badge ${statusInfo.className}` });
        host.updateText(badge, statusInfo.label);
        host.appendToElement(header, name);
        host.appendToElement(header, badge);
        host.appendToElement(info, header);

        const meta = host.createElement('div', { class: 'rag-document-meta' });
        const metaParts: string[] = [];
        if (isNumber(item.fileSizeBytes)) {
            metaParts.push(formatBytes(item.fileSizeBytes));
        }
        if (isNumber(item.createdAtMs)) {
            metaParts.push(i18n.formatDate(new Date(item.createdAtMs)));
        }
        if (metaParts.length > 0) {
            host.updateText(meta, metaParts.join(' • '));
            host.appendToElement(info, meta);
        }
        if (isNumber(item.totalChunks) && isNumber(item.processedChunks)) {
            const chunkLabel = i18n.t('chat.configuration.rag.chunks', {
                processed: item.processedChunks,
                total: item.totalChunks
            });
            const chunkLine = host.createElement('div', { class: 'rag-document-chunks' });
            host.updateText(chunkLine, chunkLabel);
            host.appendToElement(info, chunkLine);
        }

        const isProcessing = isRagDocumentProcessingStatus(item.status);
        if (!isProcessing && ragDocumentProgress.has(item.id)) {
            ragDocumentProgress.delete(item.id);
        }
        if (isProcessing) {
            const progressContainer = host.createElement('div', {
                class: 'rag-document-progress',
                role: 'progressbar',
                'aria-valuemin': '0',
                'aria-valuemax': '100'
            });
            const progressBar = host.createElement('div', { class: 'rag-document-progress-bar' });
            const trackedProgress = ragDocumentProgress.get(item.id);
            const hasTrackedProgress = isNumber(trackedProgress) && trackedProgress > 0;
            if (hasTrackedProgress) {
                const percent = normalizeProgressPercent(trackedProgress);
                if (percent === null) {
                    throw new Error('RAG document tracked progress is invalid');
                }
                syncRagDocumentProgress(host, progressBar, progressContainer, percent);
            } else {
                const totalChunks = isNumber(item.totalChunks) ? item.totalChunks : 0;
                const processedChunks = isNumber(item.processedChunks) ? item.processedChunks : 0;
                const percent = normalizeProgressParts(processedChunks, totalChunks);
                if (percent !== null) {
                    syncRagDocumentProgress(host, progressBar, progressContainer, percent);
                } else {
                    host.updateAttribute(progressBar, 'data-indeterminate', 'true');
                }
            }
            host.appendToElement(progressContainer, progressBar);
            host.appendToElement(info, progressContainer);
        }

        const detailText = item.status === 'error' ? (item.errorMessage ?? item.statusDetails) : item.statusDetails;
        if (isString(detailText) && detailText) {
            const detail = host.createElement('div', { class: 'rag-document-detail' });
            host.updateText(detail, detailText);
            host.appendToElement(info, detail);
        }

        const actions = host.createElement('div', { class: 'rag-document-actions' });
        const deleteLabel = i18n.t('common.delete');
        const deleteBtn = host.createElement('button', {
            class: 'ui-round-button ui-round-button--inline ui-round-button--delete rag-document-delete',
            type: 'button',
            'data-doc-id': item.id,
            'aria-label': deleteLabel
        });
        setTooltipText(deleteBtn, deleteLabel);
        replaceChildrenFromTrustedHtml({ element: deleteBtn, html: getIconSync('close', { size: 14, strokeWidth: 1.5 }), context: deleteBtn });
        host.appendToElement(actions, deleteBtn);
        host.appendToElement(row, leadingIcon);
        host.appendToElement(row, info);
        host.appendToElement(row, actions);
        fragment.appendChild(row);
    });
    host.appendToElement(container, fragment);
    checkerboardService.applyCheckerboard(container, '.rag-document-item', offset);

    const canPrev = offset > 0;
    const canNext = offset + limit < count;
    const showPager = Number.isFinite(count) && Number.isFinite(limit) && Number.isFinite(offset) && count > 0 && limit > 0 && (canPrev || canNext);
    if (!showPager) {
        return;
    }
    const start = Math.min(count, offset + 1);
    const end = Math.min(count, offset + documents.length);
    const pager = host.createElement('div', { class: 'rag-documents-pager' });
    const summary = host.createElement('div', { class: 'rag-documents-pager-summary' });
    host.updateText(summary, i18n.t('chat.configuration.rag.pagination.summary', { start, end, count }));
    const controls = host.createElement('div', { class: 'rag-documents-pager-controls' });
    const prevLabel = i18n.t('chat.configuration.rag.pagination.prev');
    const nextLabel = i18n.t('chat.configuration.rag.pagination.next');
    const prevOffset = Math.max(0, offset - limit);
    const nextOffset = offset + limit;
    const prevBtn = host.createElement('button', {
        class: 'ui-button ui-button--sm rag-documents-page rag-documents-prev',
        type: 'button',
        disabled: !canPrev,
        'data-rag-offset': String(prevOffset),
        'aria-label': prevLabel
    });
    host.updateText(prevBtn, prevLabel);
    setTooltipText(prevBtn, prevLabel);
    const nextBtn = host.createElement('button', {
        class: 'ui-button ui-button--sm rag-documents-page rag-documents-next',
        type: 'button',
        disabled: !canNext,
        'data-rag-offset': String(nextOffset),
        'aria-label': nextLabel
    });
    host.updateText(nextBtn, nextLabel);
    setTooltipText(nextBtn, nextLabel);
    host.appendToElement(controls, prevBtn);
    host.appendToElement(controls, nextBtn);
    host.appendToElement(pager, summary);
    host.appendToElement(pager, controls);
    host.appendToElement(container, pager);
};

export { renderRagDocumentsList };
