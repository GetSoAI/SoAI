/* SoAI - Shared animations contracts [frontend/assets/ts/core/animations/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type HeaderState = 'EXTENDED' | 'FOLDED' | null;

interface PageHeaderAnimatorProxy {
    initialize: () => void;
    attach: (scrollContainer: HTMLElement) => void;
    detach: (scrollContainer: HTMLElement) => void;
    setScrollTopWithoutReaction: (scrollContainer: HTMLElement, scrollTop: number) => void;
}

export type { HeaderState, PageHeaderAnimatorProxy };
