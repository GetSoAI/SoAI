/* SoAI - Attachment dialog SoAI link input and lookup lifetime [frontend/assets/ts/features/attachmodal/AttachLinkController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { createAbortSignalScope, isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { containsSoaiPathToken, extractSoaiPathTokenTexts, requireSoaiVirtualPath, stripSoaiPathTokensForDisplay } from '@core/soailinks/codec.ts';
import { setFieldErrorMessage } from '@core/ui/forms/fieldError.ts';
import type { AttachDraftListController } from '@features/attachmodal/AttachDraftListController.ts';
import type { AttachLinkElements } from '@features/attachmodal/contracts.ts';

interface AttachLinkConsumer {
    captureLookup(): (value: string, signal: AbortSignal, isCurrent: () => boolean) => Promise<boolean>;
    run(task: () => Promise<void>): void;
}

class AttachLinkController {
    readonly #consumer: AttachLinkConsumer;
    readonly #elements: AttachLinkElements;
    readonly #signal: AbortSignal;
    readonly #drafts: AttachDraftListController;
    readonly #sequence = new SequenceToken();
    #controller: AbortController | null = null;
    #active = false;

    constructor(consumer: AttachLinkConsumer, elements: AttachLinkElements, signal: AbortSignal, drafts: AttachDraftListController) {
        this.#consumer = consumer;
        this.#elements = elements;
        this.#signal = signal;
        this.#drafts = drafts;
        elements.input.addEventListener('input', this.#input, { signal });
        elements.input.addEventListener(
            'paste',
            (event) => {
                const text = event.clipboardData?.getData('text/plain') ?? '';
                if (!containsSoaiPathToken(text)) return;
                event.preventDefault();
                elements.input.value = this.#resolvePastedValue(elements.input, text);
                this.#input();
            },
            { signal }
        );
        signal.addEventListener('abort', this.deactivate, { once: true });
    }

    activate(): void {
        const wasActive = this.#active;
        this.#active = true;
        this.#drafts.activate();
        if (!wasActive) this.#input();
    }
    readonly deactivate = (): void => {
        this.#active = false;
        this.#sequence.invalidate();
        this.#controller?.abort();
        this.#controller = null;
        this.#drafts.deactivate();
    };
    readonly #input = (): void => {
        this.#controller?.abort();
        const token = this.#sequence.next();
        const value = this.#elements.input.value;
        let complete = false;
        try {
            const tokens = extractSoaiPathTokenTexts(value);
            for (const item of tokens) requireSoaiVirtualPath(item.virtualPath);
            complete = tokens.length > 0 && !containsSoaiPathToken(stripSoaiPathTokensForDisplay(value));
        } catch {
            complete = false;
        }
        setFieldErrorMessage(this.#elements.input, this.#elements.error, value.trim() && !complete ? i18n.t('chat.attachModal.soaiLinkSubtitle') : null);
        if (!complete || !this.#active || this.#signal.aborted) return;
        const lookup = this.#consumer.captureLookup();
        const controller = new AbortController();
        this.#controller = controller;
        const scope = createAbortSignalScope([this.#signal, controller.signal]);
        const isCurrent = (): boolean => this.#active && !scope.signal.aborted && this.#sequence.isActive(token) && this.#elements.input.value === value;
        this.#consumer.run(async () => {
            try {
                if (!isCurrent()) return;
                const accepted = await lookup(value, scope.signal, isCurrent);
                if (!accepted || !isCurrent()) return;
                this.#elements.input.value = '';
                setFieldErrorMessage(this.#elements.input, this.#elements.error, null);
            } catch (error) {
                if (isCurrent() && !isAbortError(error)) throw ensureError(error);
            } finally {
                scope.cleanup();
                if (this.#controller === controller) this.#controller = null;
            }
        });
    };

    #resolvePastedValue(input: HTMLTextAreaElement, pastedText: string): string {
        const start = input.selectionStart ?? input.value.length;
        const end = input.selectionEnd ?? input.value.length;
        return `${input.value.slice(0, start)}${pastedText}${input.value.slice(end)}`;
    }
}

export { AttachLinkController };
export type { AttachLinkConsumer };
