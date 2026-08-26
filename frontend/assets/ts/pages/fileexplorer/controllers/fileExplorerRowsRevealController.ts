/* SoAI - File Explorer rows reveal controller [frontend/assets/ts/pages/fileexplorer/controllers/fileExplorerRowsRevealController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getCancelAnimationFrame, getRequestAnimationFrame } from '@core/environment/public.ts';
import { areCollectionCardRevealAnimationsDisabled, armCollectionCardRevealTargetsAtIndex, clearCollectionCardRevealHydrating, markCollectionCardRevealHydrating, releaseCollectionCardReveal, stageCollectionCardReveal } from '@core/collectionpage/cardReveal.ts';

const FILE_EXPLORER_ROW_ENTERING_CLASS = 'entering';
const FILE_EXPLORER_ICON_REVEAL_STEP_MS = 8;

class FileExplorerRowsRevealController {
    readonly #root: HTMLElement;
    readonly #rowsBody: HTMLTableSectionElement;
    readonly #requestAnimationFrame: (callback: FrameRequestCallback) => number;
    readonly #cancelAnimationFrame: (handle: number) => void;
    #releaseFrame: number | null = null;
    #autoRelease = true;

    constructor(dependencies: { root: HTMLElement; rowsBody: HTMLTableSectionElement }) {
        this.#root = dependencies.root;
        this.#rowsBody = dependencies.rowsBody;
        this.#requestAnimationFrame = getRequestAnimationFrame();
        this.#cancelAnimationFrame = getCancelAnimationFrame();
    }

    reveal(): void {
        this.#cancelPendingRelease();
        stageCollectionCardReveal(this.#root, null);
        markCollectionCardRevealHydrating(this.#rowsBody);
        let shouldRelease = true;
        try {
            if (!areCollectionCardRevealAnimationsDisabled(this.#rowsBody)) {
                let index = 0;
                for (const child of Array.from(this.#rowsBody.children)) {
                    if (!(child instanceof HTMLElement)) {
                        continue;
                    }
                    child.classList.remove(FILE_EXPLORER_ROW_ENTERING_CLASS);
                    child.style.removeProperty('--collection-enter-delay');
                    this.#armRevealTarget(child, index);
                    index += 1;
                }
                shouldRelease = index > 0;
            }
        } finally {
            clearCollectionCardRevealHydrating(this.#rowsBody);
        }
        if (!shouldRelease || !this.#autoRelease) {
            return;
        }
        this.releaseNextFrame();
    }

    holdRelease(): void {
        this.#autoRelease = false;
        this.#cancelPendingRelease();
    }

    resumeAutoRelease(): void {
        this.#autoRelease = true;
    }

    releaseNow(): void {
        this.#cancelPendingRelease();
        releaseCollectionCardReveal(this.#root, null);
    }

    releaseNextFrame(): void {
        this.#cancelPendingRelease();
        this.#releaseFrame = this.#requestAnimationFrame(() => {
            this.#releaseFrame = null;
            releaseCollectionCardReveal(this.#root, null);
        });
    }

    dispose(): void {
        this.#cancelPendingRelease();
    }

    #cancelPendingRelease(): void {
        if (this.#releaseFrame === null) {
            return;
        }
        this.#cancelAnimationFrame(this.#releaseFrame);
        this.#releaseFrame = null;
    }

    #armRevealTarget(child: HTMLElement, index: number): void {
        if (this.#root.dataset['viewMode'] !== 'icons') {
            armCollectionCardRevealTargetsAtIndex(child, index);
            return;
        }
        armCollectionCardRevealTargetsAtIndex(child, index);
        child.style.setProperty('--collection-enter-delay', `${index * FILE_EXPLORER_ICON_REVEAL_STEP_MS}ms`);
    }
}

export { FileExplorerRowsRevealController };
