/* SoAI - PTY terminal view [frontend/assets/ts/features/terminal/PTYTerminalView.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import { Terminal } from '@xterm/xterm';
import { ensureError } from '@core/errors/coerce.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { runAsyncCleanupStepCollectingFailure, runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';
import { measureElementLayoutDimensions } from '@core/layout/elementGeometry.ts';
import { isAvailableFocusTarget } from '@core/dom/focusTarget.ts';
import { createAbortError } from '@core/errors/abort.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { buildTerminalTheme } from '@features/terminal/ptyTerminalTheme.ts';
import { TERMINAL_FONT_SIZE, type PTYTerminalConfig } from '@features/terminal/PTYTerminalViewSupport.ts';
import { PtyTerminalSession } from '@features/terminal/ptyTerminalSession.ts';
import { TerminalTextViewportScale } from '@features/terminal/terminalTextViewportScale.ts';

class PTYTerminalView {
    readonly #xterm: Terminal;
    readonly #fitAddon: FitAddon;
    readonly #session: PtyTerminalSession;
    readonly #config: PTYTerminalConfig;
    readonly #timers = new ResourceTracker();
    readonly #textViewportScale: TerminalTextViewportScale;
    #baseFontSize: number;
    #resizeObserver: ResizeObserver | null = null;
    #resizeTimeout: number | null = null;
    #mounted: boolean = false;
    #disposed: boolean = false;
    #disposal: Promise<void> | null = null;

    constructor(config: PTYTerminalConfig) {
        this.#config = config;
        this.#textViewportScale = new TerminalTextViewportScale(config.container, this.#handleTextViewportScaleChanged);
        this.#baseFontSize = clampNumber(config.fontSize ?? TERMINAL_FONT_SIZE.DEFAULT, TERMINAL_FONT_SIZE.MIN, TERMINAL_FONT_SIZE.MAX);
        this.#xterm = new Terminal({
            cursorBlink: true,
            cursorStyle: 'block',
            fontFamily: "ui-monospace, 'Cascadia Code', 'Source Code Pro', Menlo, Consolas, 'DejaVu Sans Mono', monospace",
            fontSize: this.#resolveRenderedFontSize(),
            lineHeight: 1,
            scrollback: 10000,
            allowProposedApi: true,
            theme: buildTerminalTheme()
        });
        this.#fitAddon = new FitAddon();
        this.#xterm.loadAddon(this.#fitAddon);
        this.#xterm.loadAddon(new WebLinksAddon());
        this.#session = new PtyTerminalSession({ terminal: this.#xterm, fitAddon: this.#fitAddon, config: this.#config });
    }

    get busy(): boolean {
        return this.#session.busy;
    }

    async mount(signal?: AbortSignal): Promise<void> {
        if (this.#disposed) throw createAbortError('PTY terminal view is disposed');
        if (this.#mounted) throw new Error('PTY terminal view is already mounted');
        this.#config.owner.admission.requireActive();
        this.#xterm.open(this.#config.container);
        this.#mounted = true;
        this.#fitTerminal();
        this.#setupResizeObserver();
        this.#textViewportScale.observe();
        let visible = this.#config.owner.presentation.isVisible();
        const observePresentation = this.#config.owner.presentation.subscribe(() => {
            const nextVisible = this.#config.owner.presentation.isVisible();
            if (nextVisible && !visible) this.#scheduleFit();
            visible = nextVisible;
        });
        this.#timers.track(observePresentation, (release) => release());
        this.#session.initialize();
        await this.#session.connect(signal);
    }

    clear(): void {
        this.#session.clear();
    }

    focus(): void {
        if (!this.#disposed && this.#config.owner.presentation.isFocused() && this.#config.container.isConnected && isAvailableFocusTarget(this.#config.container)) this.#xterm.focus();
    }

    get fontSize(): number {
        return this.#baseFontSize;
    }

    set fontSize(size: number) {
        if (this.#disposed || !this.#config.owner.admission.canMutate()) return;
        this.#baseFontSize = clampNumber(size, TERMINAL_FONT_SIZE.MIN, TERMINAL_FONT_SIZE.MAX);
        this.#applyRenderedFontSize();
    }

    dispose(): Promise<void> {
        if (this.#disposal) return this.#disposal;
        const completion = createDeferred<void>();
        this.#disposal = completion.promise;
        this.#disposed = true;
        this.#mounted = false;
        const failures: Error[] = [];
        const releases = [runAsyncCleanupStepCollectingFailure(() => this.#session.dispose(), failures), runAsyncCleanupStepCollectingFailure(() => this.#timers.dispose(), failures)];
        runCleanupStepCollectingFailure(() => this.#textViewportScale.dispose(), failures);
        runCleanupStepCollectingFailure(() => {
            this.#resizeObserver?.disconnect();
            this.#resizeObserver = null;
        }, failures);
        runCleanupStepCollectingFailure(() => this.#xterm.dispose(), failures);
        void Promise.all(releases)
            .then(() => throwCollectedCleanupFailures(failures))
            .then(completion.resolve, (error) => completion.reject(ensureError(error)));
        return completion.promise;
    }

    #resolveRenderedFontSize(): number {
        return this.#baseFontSize * this.#textViewportScale.scale;
    }

    #applyRenderedFontSize(): void {
        if (!this.#config.owner.presentation.isVisible()) return;
        this.#xterm.options.fontSize = this.#resolveRenderedFontSize();
        if (!this.#mounted) return;
        this.#scheduleFit();
    }

    #fitTerminal(): void {
        if (this.#disposed || !this.#mounted || !this.#config.container.isConnected || !this.#config.owner.presentation.isVisible()) return;
        const dimensions = measureElementLayoutDimensions(this.#config.container);
        if (dimensions.width <= 0 || dimensions.height <= 0) return;
        this.#xterm.options.fontSize = this.#resolveRenderedFontSize();
        this.#fitAddon.fit();
        this.#session.sendResize();
    }

    #scheduleFit = (): void => {
        if (this.#disposed) return;
        if (this.#resizeTimeout !== null) this.#timers.clearTimer(this.#resizeTimeout);
        this.#resizeTimeout = this.#timers.setTimeout(() => {
            this.#resizeTimeout = null;
            this.#fitTerminal();
        }, 100);
    };

    readonly #handleTextViewportScaleChanged = (): void => {
        if (this.#disposed) return;
        this.#applyRenderedFontSize();
    };

    #setupResizeObserver(): void {
        this.#resizeObserver = new ResizeObserver(this.#scheduleFit);
        this.#resizeObserver.observe(this.#config.container);
    }
}

export { PTYTerminalView };
export { TERMINAL_FONT_SIZE };
export type { PTYTerminalConfig };
