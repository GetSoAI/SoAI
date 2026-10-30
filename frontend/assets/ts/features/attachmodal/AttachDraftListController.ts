/* SoAI - Attachment draft list lifecycle and removal interaction [frontend/assets/ts/features/attachmodal/AttachDraftListController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { bindTypedResolvedDataActionListener } from '@core/dom/dataActionBinding.ts';
import { createBusyDisabledToken, setBusyDisabledState, type BusyDisabledToken } from '@core/ui/controls/busyDisabledState.ts';
import type { AttachDraftListElements } from '@features/attachmodal/contracts.ts';
import type { AttachDraftConsumer, AttachDraftPresentation } from '@features/attachmodal/draftContracts.ts';
import { renderDraftAttachmentListState } from '@features/attachmodal/draftState.ts';

class AttachDraftListController {
    readonly #consumer: AttachDraftConsumer;
    readonly #elements: AttachDraftListElements;
    readonly #presentation: AttachDraftPresentation;
    readonly #signal: AbortSignal;
    #unsubscribe: (() => void) | null = null;
    readonly #pending = new Map<HTMLButtonElement, BusyDisabledToken>();

    constructor(consumer: AttachDraftConsumer, elements: AttachDraftListElements, signal: AbortSignal, presentation: AttachDraftPresentation) {
        this.#consumer = consumer;
        this.#elements = elements;
        this.#presentation = presentation;
        this.#signal = signal;
        bindTypedResolvedDataActionListener({
            root: elements.list,
            signal,
            eventType: 'click',
            isAction: (action): action is 'attach-draft:remove' => action === 'attach-draft:remove',
            preventDefault: 'always',
            onAction: ({ actionElement }) => this.#remove(actionElement)
        });
        signal.addEventListener(
            'abort',
            () => {
                this.#stopSubscription();
                for (const [button, token] of this.#pending) setBusyDisabledState(button, { isBusy: false, token });
                this.#pending.clear();
            },
            { once: true }
        );
        this.#render();
    }

    activate(): void {
        if (this.#signal.aborted || this.#unsubscribe !== null) return;
        this.#unsubscribe = this.#consumer.subscribe(() => this.#render());
        this.#render();
    }

    readonly deactivate = (): void => {
        this.#stopSubscription();
    };

    #stopSubscription(): void {
        const unsubscribe = this.#unsubscribe;
        this.#unsubscribe = null;
        unsubscribe?.();
    }

    #remove(element: HTMLElement): void {
        if (!(element instanceof HTMLButtonElement) || this.#pending.has(element) || this.#signal.aborted) return;
        const id = element.dataset['fileId'];
        if (!id) throw new Error('Draft removal requires an attachment identity');
        this.#pending.set(element, setBusyDisabledState(element, { isBusy: true, createToken: createBusyDisabledToken }));
        this.#consumer.run(async () => {
            try {
                await this.#consumer.remove(id);
            } finally {
                const token = this.#pending.get(element);
                this.#pending.delete(element);
                if (token !== undefined && !this.#signal.aborted) setBusyDisabledState(element, { isBusy: false, token });
            }
        });
    }

    #render(): void {
        if (this.#signal.aborted) return;
        const entries = this.#consumer.snapshot();
        renderDraftAttachmentListState(this.#elements, entries, entries.filter((entry) => entry.attachment.parseStatus === 'processing').length, entries.filter((entry) => entry.attachment.parseStatus === 'ready').length, this.#presentation);
        this.#presentation.afterRender(entries);
    }
}

export { AttachDraftListController };
