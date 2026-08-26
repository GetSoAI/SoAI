/* SoAI - Chat attachment overflow modal auto paging [frontend/assets/ts/features/chat/message/attachmentoverflowmodal/autoPager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

class AttachmentOverflowAutoPager {
    readonly #onReveal: () => void;
    #observer: IntersectionObserver | null = null;
    #root: HTMLElement | null = null;
    #sentinel: HTMLElement | null = null;
    #enabled = false;

    constructor(onReveal: () => void) {
        this.#onReveal = onReveal;
    }

    update(root: HTMLElement | null, sentinel: HTMLElement | null, enabled: boolean): void {
        const rootChanged = this.#root !== root;
        const sentinelChanged = this.#sentinel !== sentinel;
        const enabledChanged = this.#enabled !== enabled;
        this.#root = root;
        this.#sentinel = sentinel;
        this.#enabled = enabled;
        if (rootChanged || sentinelChanged || enabledChanged) {
            this.#syncObserver();
        }
    }

    dispose(): void {
        this.#observer?.disconnect();
        this.#observer = null;
        this.#root = null;
        this.#sentinel = null;
        this.#enabled = false;
    }

    #syncObserver(): void {
        this.#observer?.disconnect();
        this.#observer = null;
        if (!this.#enabled || this.#sentinel === null) {
            return;
        }
        const observer = new IntersectionObserver(
            (entries: IntersectionObserverEntry[]): void => {
                for (const entry of entries) {
                    if (entry.target !== this.#sentinel || !entry.isIntersecting) {
                        continue;
                    }
                    this.#onReveal();
                    break;
                }
            },
            {
                root: this.#root,
                rootMargin: '0px 0px 240px 0px',
                threshold: 0
            }
        );
        this.#observer = observer;
        observer.observe(this.#sentinel);
    }
}

export { AttachmentOverflowAutoPager };
