/* SoAI - Terminal page contracts [frontend/assets/ts/pages/terminal/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PTYTerminalView } from '@features/terminal/public.ts';

export interface TerminalUiRefs {
    root: HTMLElement;
    shell: HTMLElement;
}

export interface TerminalTextZoomStorage {
    getTerminalTextZoom?: (fallback: number) => number | null;
    setTerminalTextZoom?: (value: number) => void;
}

export interface TerminalSessionGuard {
    cleanup: (() => void) | null;
    view: PTYTerminalView | null;
}
