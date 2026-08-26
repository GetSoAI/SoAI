/* SoAI - Chat attach modal linked knowledge view [frontend/assets/ts/pages/chat/controllers/modals/chatattach/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import type { ElementOptions } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderInlineLoadingStatus } from '@core/ui/loadingStatus.ts';
import { countProcessingRagDocuments, isRagDocumentProcessingStatus, renderRagDocumentsList, type RagConfig, type RagDocument, type RagDocumentsPage } from '@features/chat/public.ts';
import type { ChatAttachKnowledgeCapabilities } from '@pages/chat/controllers/modals/chatattach/chatAttachKnowledgeCapabilitiesController.ts';
import type { ChatAttachKnowledgeElements } from '@pages/chat/controllers/modals/chatattach/types.ts';

const setButtonEnabled = (button: HTMLButtonElement, enabled: boolean): void => {
    button.disabled = !enabled;
    button.setAttribute('aria-disabled', enabled ? 'false' : 'true');
};

const openFilePicker = (input: HTMLInputElement): void => {
    if (typeof input.showPicker === 'function') {
        input.showPicker();
        return;
    }
    input.click();
};

const createDomHost = (documentRef: Document): { dom: { getDocument: () => Document; setStyle: (element: HTMLElement, prop: string, value: string | null) => void }; createElement: (tag: string, options?: ElementOptions, content?: string | Node) => HTMLElement; appendToElement: (parent: Element, child: Node | Node[]) => void; updateHTML: (element: Element, html: string) => void; updateText: (element: Element, text: string) => void; updateProperty: (element: Element, prop: string, value: DomPropertyValue) => void; updateAttribute: (element: Element, attr: string, value: string | null) => void; toggleClassName: (element: Element, className: string, add: boolean) => void } => ({
    dom: {
        getDocument: (): Document => documentRef,
        setStyle: (element: HTMLElement, prop: string, value: string | null): void => {
            if (value === null) {
                element.style.removeProperty(prop);
                return;
            }
            element.style.setProperty(prop, value);
        }
    },
    createElement: (tag: string, options: ElementOptions = {}, content?: string | Node): HTMLElement => {
        const element = documentRef.createElement(tag);
        for (const [name, value] of Object.entries(options)) {
            if (value === null || value === undefined || value === false) {
                continue;
            }
            if (name === 'class') {
                element.className = String(value);
                continue;
            }
            if (name === 'disabled' && value === true && element instanceof HTMLButtonElement) {
                element.disabled = true;
                continue;
            }
            element.setAttribute(name, String(value));
        }
        if (typeof content === 'string') {
            element.textContent = content;
        } else if (content !== undefined) {
            element.append(content);
        }
        return element;
    },
    appendToElement: (parent: Element, child: Node | Node[]): void => {
        if (Array.isArray(child)) {
            parent.append(...child);
            return;
        }
        parent.append(child);
    },
    updateHTML: (element: Element, html: string): void => {
        element.textContent = html;
    },
    updateText: (element: Element, text: string): void => {
        element.textContent = text;
    },
    updateProperty: (element: Element, prop: string, value: DomPropertyValue): void => {
        if (prop === 'disabled' && element instanceof HTMLButtonElement) {
            element.disabled = value === true;
        }
    },
    updateAttribute: (element: Element, attr: string, value: string | null): void => {
        if (value === null) {
            element.removeAttribute(attr);
            return;
        }
        element.setAttribute(attr, value);
    },
    toggleClassName: (element: Element, className: string, add: boolean): void => {
        element.classList.toggle(className, add);
    }
});

const resolveRagStatus = (document: RagDocument): { label: string; className: string } => {
    switch (document.status) {
        case 'queued':
            return { label: i18n.t('chat.configuration.rag.status.queued'), className: 'status-blue' };
        case 'parsing':
            return { label: i18n.t('chat.configuration.rag.status.parsing'), className: 'status-blue' };
        case 'fetching':
            return { label: i18n.t('chat.configuration.rag.status.fetching'), className: 'status-blue' };
        case 'chunking':
            return { label: i18n.t('chat.configuration.rag.status.chunking'), className: 'status-blue' };
        case 'embedding':
            return { label: i18n.t('chat.configuration.rag.status.embedding'), className: 'status-blue' };
        case 'completed':
            return { label: i18n.t('chat.configuration.rag.status.completed'), className: 'status-green' };
        case 'error':
            if (document.statusDetails === 'unreadable') {
                return { label: i18n.t('chat.configuration.rag.status.unreadable'), className: 'status-red' };
            }
            return {
                label: i18n.t('chat.configuration.rag.status.error'),
                className: 'status-red'
            };
        default:
            return { label: i18n.t('chat.configuration.rag.status.unknown'), className: 'status-grey' };
    }
};

const syncKnowledgeActions = (elements: ChatAttachKnowledgeElements, config: RagConfig | null, page: RagDocumentsPage | null, capabilities: ChatAttachKnowledgeCapabilities): void => {
    setButtonEnabled(elements.dropzoneButton, capabilities.documentsEnabled || capabilities.foldersEnabled);
    setButtonEnabled(elements.documentsButton, capabilities.documentsEnabled);
    setButtonEnabled(elements.folderButton, capabilities.foldersEnabled);
    setButtonEnabled(elements.importButton, true);
    const hasDocuments = page !== null && page.count > 0;
    elements.reindexButton.hidden = !hasDocuments;
    setButtonEnabled(elements.reindexButton, hasDocuments && Boolean(config?.embeddingModel));
};

const selectFinalizedRagDocuments = (documents: RagDocument[]): RagDocument[] => {
    return documents.filter((document) => !isRagDocumentProcessingStatus(document.status));
};

const knowledgeDocumentsSignature = (finalizedDocuments: RagDocument[], page: RagDocumentsPage): string => {
    const rows = finalizedDocuments.map((document) => `${document.id}:${document.status}:${document.errorMessage ?? ''}:${document.processedChunks ?? ''}/${document.totalChunks ?? ''}`).join('|');
    return `${rows}#${page.count}@${page.offset}@${page.limit}`;
};

const renderKnowledgeDocuments = (elements: ChatAttachKnowledgeElements, page: RagDocumentsPage, rebuildList: boolean, finalizedDocuments: RagDocument[]): void => {
    const processing = countProcessingRagDocuments(page.statusCounts);
    renderInlineLoadingStatus(elements.summary, {
        text: i18n.t('chat.configuration.knowledge.summary', {
            documents: page.count,
            chunks: page.chunkCount,
            completed: page.statusCounts.completed,
            processing,
            errors: page.statusCounts.error
        }),
        loading: processing > 0
    });
    elements.summary.classList.toggle('u-hidden', page.count === 0);
    if (page.count === 0) {
        elements.list.replaceChildren();
        return;
    }
    if (rebuildList) {
        renderRagDocumentsList({
            host: createDomHost(elements.list.ownerDocument),
            container: elements.list,
            emptyState: null,
            documents: finalizedDocuments,
            count: page.count,
            limit: page.limit,
            offset: page.offset,
            ragDocumentProgress: new Map<string, number>(),
            resolveRagStatus
        });
    }
};

const renderKnowledgeNoConversation = (elements: ChatAttachKnowledgeElements): void => {
    renderInlineLoadingStatus(elements.summary, { text: '', loading: false });
    elements.list.replaceChildren();
};

export { knowledgeDocumentsSignature, openFilePicker, renderKnowledgeDocuments, renderKnowledgeNoConversation, selectFinalizedRagDocuments, setButtonEnabled, syncKnowledgeActions };
