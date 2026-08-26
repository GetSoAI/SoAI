/* SoAI - Terminal feature text viewport scale [frontend/assets/ts/features/terminal/terminalTextViewportScale.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutViewport } from '@core/layout/elementGeometry.ts';
import { INTERFACE_SCALE_CHANGED_EVENT } from '@core/layout/interfaceScale.ts';

interface TerminalTextScaleBreakpoint {
    readonly maxWidth: number;
    readonly scale: number;
}

const TERMINAL_TEXT_SCALE_BREAKPOINTS: ReadonlyArray<TerminalTextScaleBreakpoint> = Object.freeze([Object.freeze({ maxWidth: 480, scale: 0.7 }), Object.freeze({ maxWidth: 900, scale: 0.85 })]);

const TERMINAL_TEXT_SCALE_FULL = 1;

class TerminalTextViewportScale {
    readonly #scope: Element;
    readonly #onScaleChanged: () => void;
    #abortController: AbortController | null = null;

    constructor(scope: Element, onScaleChanged: () => void) {
        this.#scope = scope;
        this.#onScaleChanged = onScaleChanged;
    }

    get scale(): number {
        const width = measureLayoutViewport(this.#scope).width;
        for (const breakpoint of TERMINAL_TEXT_SCALE_BREAKPOINTS) {
            if (width <= breakpoint.maxWidth) {
                return breakpoint.scale;
            }
        }
        return TERMINAL_TEXT_SCALE_FULL;
    }

    observe(): void {
        if (this.#abortController) return;
        this.#abortController = new AbortController();
        const signal = this.#abortController.signal;
        const windowRef = this.#scope.ownerDocument.defaultView;
        if (!windowRef) throw new Error('Terminal text viewport scale requires a document window');
        windowRef.addEventListener('resize', this.#handleViewportChange, { signal });
        windowRef.addEventListener(INTERFACE_SCALE_CHANGED_EVENT, this.#handleViewportChange, { signal });
    }

    dispose(): void {
        this.#abortController?.abort();
        this.#abortController = null;
    }

    readonly #handleViewportChange = (): void => {
        this.#onScaleChanged();
    };
}

export { TerminalTextViewportScale };
