/* SoAI - Shared UI text controller [frontend/assets/ts/core/ui/modals/contentpreview/textController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { requireModalPresenter, type ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { requireSyntaxHighlighter } from '@core/syntaxhighlighter/public.ts';
import { requireContentPreviewTextHost, requireContentPreviewTextStatsHost, requireContentPreviewTitleHost } from '@core/ui/modals/contentpreview/dom.ts';
import { createEmptyContentPreviewTextBaseline, normalizeContentPreviewTextBaseline } from '@core/ui/modals/contentpreview/textBaseline.ts';
import { hideContentPreviewTextStats, renderContentPreviewTextStats } from '@core/ui/modals/contentpreview/textStats.ts';
import type { ContentPreviewTextBaseline, ContentPreviewTextDraftSnapshot, ContentPreviewTextRequest } from '@core/ui/modals/contentpreview/types.ts';

const renderHighlightedText = (host: HTMLElement, content: string, languageMode: ContentPreviewTextRequest['languageMode']): void => {
    host.textContent = '';
    host.classList.remove('prompt-view-text--editing');
    host.classList.add('prompt-view-text');
    host.classList.add('prompt-modal-content-text');

    const highlighter = requireSyntaxHighlighter();
    const detected = highlighter.detectLanguage(content);
    const language = languageMode === 'plaintextIfSql' && detected === 'sql' ? 'plaintext' : detected;
    const highlighted = highlighter.highlight(content, language);
    host.append(highlighted);
};

type ContentPreviewTextController = {
    reset: (modalRoot: HTMLElement) => void;
    isEditing: () => boolean;
    enterEditMode: (modalRoot: HTMLElement, request: ContentPreviewTextRequest) => void;
    exitEditMode: (modalRoot: HTMLElement, request: ContentPreviewTextRequest) => void;
    renderViewMode: (modalRoot: HTMLElement, request: ContentPreviewTextRequest) => void;
    hasDraftChanges: () => boolean;
    getDraftSnapshot: (modalRoot: HTMLElement) => ContentPreviewTextDraftSnapshot | null;
    setSelectedColor: (modalRoot: HTMLElement, color: string | null) => void;
    applySavedBaseline: (modalRoot: HTMLElement, request: ContentPreviewTextRequest, nextBaseline: ContentPreviewTextBaseline) => ContentPreviewTextBaseline;
};

const createContentPreviewTextController = (resources: ResourceTracker): ContentPreviewTextController => {
    const modalPresenter: ModalPresenterApi = requireModalPresenter();
    let baseline: ContentPreviewTextBaseline = createEmptyContentPreviewTextBaseline();
    let draft: ContentPreviewTextDraftSnapshot | null = null;
    let editing = false;
    let resizeObserver: ResizeObserver | null = null;

    type ContentPreviewEditInputs = {
        titleInput: HTMLInputElement;
        textarea: HTMLTextAreaElement;
    };

    const resolveEditInputs = (modalRoot: HTMLElement, options: { required: boolean }): ContentPreviewEditInputs | null => {
        const titleHost = requireContentPreviewTitleHost(modalRoot);
        const titleInputCandidate = dom.resolve('.prompt-modal-title-input', titleHost);
        const titleInput = titleInputCandidate instanceof HTMLInputElement ? titleInputCandidate : null;
        const textHost = requireContentPreviewTextHost(modalRoot);
        const textareaCandidate = dom.resolve('.prompt-modal-content-textarea', textHost);
        const textarea = textareaCandidate instanceof HTMLTextAreaElement ? textareaCandidate : null;
        if (!titleInput || !textarea) {
            if (options.required) {
                throw new Error('Content preview modal edit inputs are missing');
            }
            return null;
        }
        return { titleInput, textarea };
    };

    const disposeResizeObserver = (): void => {
        if (!resizeObserver) {
            return;
        }
        resizeObserver.disconnect();
        resizeObserver = null;
    };

    const adjustTextareaHeight = (modalRoot: HTMLElement): void => {
        if (!modalPresenter.isOpen(modalRoot.id)) {
            return;
        }
        const textareaCandidate = dom.resolve('.prompt-modal-content-textarea', modalRoot);
        const textarea = textareaCandidate instanceof HTMLTextAreaElement ? textareaCandidate : null;
        if (!textarea) {
            return;
        }
        const modalBodyCandidate = dom.resolve('.modal-body', modalRoot);
        const modalBody = modalBodyCandidate instanceof HTMLElement ? modalBodyCandidate : null;
        const wasAtBottom = modalBody ? modalBody.scrollTop + modalBody.clientHeight >= modalBody.scrollHeight - 4 : false;
        const previousScrollTop = modalBody ? modalBody.scrollTop : 0;
        const { ownerDocument } = textarea;
        const windowCandidate = ownerDocument.defaultView;
        if (!windowCandidate) {
            return;
        }
        resources.requestAnimationFrame(() => {
            const styles = windowCandidate.getComputedStyle(textarea);
            const borderTop = Number.parseFloat(styles.borderTopWidth);
            const borderBottom = Number.parseFloat(styles.borderBottomWidth);
            const extra = (Number.isFinite(borderTop) ? borderTop : 0) + (Number.isFinite(borderBottom) ? borderBottom : 0);
            textarea.style.height = 'auto';
            textarea.style.height = `${Math.max(0, textarea.scrollHeight + extra)}px`;
            if (modalBody) {
                modalBody.scrollTop = wasAtBottom ? modalBody.scrollHeight : previousScrollTop;
            }
        });
    };

    const setupResizeObserver = (modalRoot: HTMLElement): void => {
        disposeResizeObserver();
        const modalContent = dom.resolve('.modal-content', modalRoot);
        if (!(modalContent instanceof HTMLElement)) {
            throw new Error('Content preview modal content is missing');
        }
        resizeObserver = new ResizeObserver(() => adjustTextareaHeight(modalRoot));
        resizeObserver.observe(modalContent);
    };

    const updateDraftFromInputs = (modalRoot: HTMLElement): void => {
        if (!editing) {
            return;
        }
        const inputs = resolveEditInputs(modalRoot, { required: true });
        if (!inputs) {
            throw new Error('Content preview modal edit inputs are missing');
        }
        draft = Object.freeze({
            title: inputs.titleInput.value,
            content: inputs.textarea.value,
            selectedColor: modalRoot.dataset['selectedColor'] ? String(modalRoot.dataset['selectedColor']) : null
        });
    };

    const resolveEffectiveDraft = (): ContentPreviewTextDraftSnapshot => {
        if (!editing || !draft) {
            return Object.freeze({
                title: baseline.title,
                content: baseline.content,
                selectedColor: baseline.promptColor
            });
        }
        return draft;
    };

    const mountEditFields = (modalRoot: HTMLElement): void => {
        const titleHost = requireContentPreviewTitleHost(modalRoot);
        titleHost.textContent = '';
        const titleInput = dom.getDocument().createElement('input');
        titleInput.type = 'text';
        titleInput.className = 'prompt-modal-title-input';
        titleInput.value = baseline.title;
        titleHost.appendChild(titleInput);

        const textHost = requireContentPreviewTextHost(modalRoot);
        textHost.classList.add('prompt-view-text--editing');
        textHost.textContent = '';
        hideContentPreviewTextStats(requireContentPreviewTextStatsHost(modalRoot));
        const textarea = dom.getDocument().createElement('textarea');
        textarea.className = 'prompt-modal-content-textarea prompt-modal-content-text prompt-view-text prompt-view-text--editing';
        textarea.value = baseline.content;
        textHost.appendChild(textarea);
        resources.addEventListener(textarea, 'input', () => adjustTextareaHeight(modalRoot), { passive: true });

        draft = Object.freeze({
            title: baseline.title,
            content: baseline.content,
            selectedColor: modalRoot.dataset['selectedColor'] ? String(modalRoot.dataset['selectedColor']) : baseline.promptColor
        });

        resources.setTimeout(() => {
            titleInput.focus();
            adjustTextareaHeight(modalRoot);
        }, 50);
    };

    const applyBaselineToModal = (modalRoot: HTMLElement, request: ContentPreviewTextRequest, nextBaseline: ContentPreviewTextBaseline): void => {
        baseline = nextBaseline;
        modalRoot.setAttribute('data-page-scope', request.scope);
        requireContentPreviewTitleHost(modalRoot).textContent = nextBaseline.title;

        if (nextBaseline.promptColor) {
            modalRoot.dataset['promptColor'] = nextBaseline.promptColor;
            modalRoot.dataset['selectedColor'] = nextBaseline.promptColor;
        } else {
            delete modalRoot.dataset['promptColor'];
            modalRoot.dataset['selectedColor'] = '';
        }

        const textHost = requireContentPreviewTextHost(modalRoot);
        renderHighlightedText(textHost, nextBaseline.content, request.languageMode);
        renderContentPreviewTextStats(requireContentPreviewTextStatsHost(modalRoot), nextBaseline.content, request.sourceReference);
    };

    return {
        reset(modalRoot: HTMLElement): void {
            disposeResizeObserver();
            hideContentPreviewTextStats(requireContentPreviewTextStatsHost(modalRoot));
            baseline = createEmptyContentPreviewTextBaseline();
            draft = null;
            editing = false;
        },
        isEditing(): boolean {
            return Boolean(editing);
        },
        renderViewMode(modalRoot: HTMLElement, request: ContentPreviewTextRequest): void {
            editing = false;
            disposeResizeObserver();
            applyBaselineToModal(modalRoot, request, request.baseline);
            baseline = request.baseline;
            draft = null;
        },
        enterEditMode(modalRoot: HTMLElement, request: ContentPreviewTextRequest): void {
            if (editing || !request.editable) {
                return;
            }
            editing = true;
            mountEditFields(modalRoot);
            setupResizeObserver(modalRoot);
        },
        exitEditMode(modalRoot: HTMLElement, request: ContentPreviewTextRequest): void {
            if (!editing) {
                return;
            }
            editing = false;
            disposeResizeObserver();
            applyBaselineToModal(modalRoot, request, baseline);
            draft = null;
        },
        hasDraftChanges(): boolean {
            if (!editing) {
                return false;
            }
            const effectiveDraft = resolveEffectiveDraft();
            const titleChanged = effectiveDraft.title !== baseline.title;
            const contentChanged = effectiveDraft.content !== baseline.content;
            const colorChanged = baseline.promptColor !== effectiveDraft.selectedColor;
            return Boolean(titleChanged || contentChanged || colorChanged);
        },
        getDraftSnapshot(modalRoot: HTMLElement): ContentPreviewTextDraftSnapshot | null {
            if (editing) {
                updateDraftFromInputs(modalRoot);
            }
            return Object.freeze({ ...resolveEffectiveDraft() });
        },
        setSelectedColor(modalRoot: HTMLElement, color: string | null): void {
            modalRoot.dataset['selectedColor'] = color ?? '';
            if (editing) {
                updateDraftFromInputs(modalRoot);
            }
        },
        applySavedBaseline(modalRoot: HTMLElement, request: ContentPreviewTextRequest, nextBaseline: ContentPreviewTextBaseline): ContentPreviewTextBaseline {
            const normalized = normalizeContentPreviewTextBaseline(nextBaseline);
            baseline = normalized;
            if (editing) {
                editing = false;
                disposeResizeObserver();
                applyBaselineToModal(modalRoot, request, normalized);
                draft = null;
                return normalized;
            }
            applyBaselineToModal(modalRoot, request, normalized);
            draft = null;
            return normalized;
        }
    };
};

export { createContentPreviewTextController };
export type { ContentPreviewTextController };
