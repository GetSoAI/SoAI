/* SoAI - Attachment overflow modal interaction controller [frontend/assets/ts/features/chat/message/attachmentoverflowmodal/interactionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { isString } from '@core/typeGuards.ts';
import { isAttachmentOverflowCategoryFilter, isKnowledgeStatusFilter, type AttachmentOverflowCategoryFilter, type KnowledgeStatusFilter } from '@features/chat/message/attachmentoverflowmodal/filters.ts';
import { TOOLBAR_CLASS_NAME } from '@features/chat/message/attachmentoverflowmodal/view.ts';

interface AttachmentOverflowInteractionControllerDependencies {
    onTab: (tab: AttachmentOverflowCategoryFilter) => void;
    onRetry: () => void;
    onRemoveDraftKnowledge: (actionElement: HTMLElement) => void;
    onKnowledgePreview: (actionElement: HTMLElement) => void;
    onKnowledgePreviewFirst: (actionElement: HTMLElement) => void;
    onSoaiPathPreview: (actionElement: HTMLElement) => void;
    onSearchSubmit: (query: string) => void;
    onStatusChange: (status: KnowledgeStatusFilter) => void;
}

class AttachmentOverflowInteractionController {
    readonly #dependencies: AttachmentOverflowInteractionControllerDependencies;
    #modal: HTMLElement | null = null;

    constructor(dependencies: AttachmentOverflowInteractionControllerDependencies) {
        this.#dependencies = dependencies;
    }

    attach(modal: HTMLElement): void {
        if (this.#modal === modal) {
            return;
        }
        this.dispose();
        modal.addEventListener('click', this.#handleClick);
        modal.addEventListener('submit', this.#handleSubmit);
        modal.addEventListener('change', this.#handleChange);
        this.#modal = modal;
    }

    dispose(): void {
        if (this.#modal === null) {
            return;
        }
        this.#modal.removeEventListener('click', this.#handleClick);
        this.#modal.removeEventListener('submit', this.#handleSubmit);
        this.#modal.removeEventListener('change', this.#handleChange);
        this.#modal = null;
    }

    readonly #handleClick = (event: Event): void => {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }
        const actionElement = target.closest('[data-attachment-overflow-action]');
        if (actionElement instanceof HTMLElement) {
            this.#handleActionClick(actionElement, event);
        }
    };

    #handleActionClick(actionElement: HTMLElement, event: Event): void {
        const action = actionElement.dataset['attachmentOverflowAction'];
        if (action === 'tab') {
            this.#handleTabClick(actionElement);
            return;
        }
        if (action === 'retry') {
            event.preventDefault();
            this.#dependencies.onRetry();
            return;
        }
        if (action === 'knowledge-remove-draft') {
            event.preventDefault();
            this.#dependencies.onRemoveDraftKnowledge(actionElement);
            return;
        }
        if (action === 'knowledge-preview') {
            event.preventDefault();
            this.#dependencies.onKnowledgePreview(actionElement);
            return;
        }
        if (action === 'knowledge-preview-first') {
            event.preventDefault();
            this.#dependencies.onKnowledgePreviewFirst(actionElement);
            return;
        }
        if (action === 'soai-path-preview') {
            event.preventDefault();
            this.#dependencies.onSoaiPathPreview(actionElement);
        }
    }

    #handleTabClick(actionElement: HTMLElement): void {
        const tab = actionElement.dataset['attachmentOverflowTab'];
        if (!isString(tab) || !isAttachmentOverflowCategoryFilter(tab)) {
            return;
        }
        this.#dependencies.onTab(tab);
    }

    readonly #handleSubmit = (event: Event): void => {
        const target = event.target;
        if (!(target instanceof HTMLFormElement) || !target.classList.contains(TOOLBAR_CLASS_NAME)) {
            return;
        }
        event.preventDefault();
        this.#dependencies.onSearchSubmit(this.#readSearchQuery(target));
    };

    readonly #handleChange = (event: Event): void => {
        const target = event.target;
        if (!(target instanceof HTMLSelectElement) || target.dataset['attachmentOverflowControl'] !== 'status') {
            return;
        }
        if (!isKnowledgeStatusFilter(target.value)) {
            return;
        }
        this.#dependencies.onStatusChange(target.value);
    };

    #readSearchQuery(form: HTMLFormElement): string {
        const input = dom.resolve('[data-attachment-overflow-control="query"]', form);
        if (!(input instanceof HTMLInputElement)) {
            return '';
        }
        return toTrimmedString(input.value);
    }
}

export { AttachmentOverflowInteractionController };
