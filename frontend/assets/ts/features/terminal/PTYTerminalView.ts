/* SoAI - PTY terminal view [frontend/assets/ts/features/terminal/PTYTerminalView.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import { Terminal } from '@xterm/xterm';
import { ensureError } from '@core/errors/coerce.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { buildTerminalTheme } from '@features/terminal/ptyTerminalTheme.ts';
import { TERMINAL_FONT_SIZE, warnTerminalError, type PTYTerminalConfig } from '@features/terminal/PTYTerminalViewSupport.ts';
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
        if (this.#disposed) return;
        this.#xterm.open(this.#config.container);
        this.#fitAddon.fit();
        this.#mounted = true;
        this.#setupResizeObserver();
        this.#textViewportScale.observe();
        this.#session.initialize();
        await this.#session.connect(signal);
    }

    clear(): void {
        this.#session.clear();
    }

    focus(): void {
        this.#xterm.focus();
    }

    get fontSize(): number {
        return this.#baseFontSize;
    }

    set fontSize(size: number) {
        this.#baseFontSize = clampNumber(size, TERMINAL_FONT_SIZE.MIN, TERMINAL_FONT_SIZE.MAX);
        this.#applyRenderedFontSize();
    }

    dispose(): void {
        if (this.#disposed) return;
        this.#disposed = true;
        this.#mounted = false;
        this.#textViewportScale.dispose();
        this.#session.dispose();
        if (this.#resizeTimeout) {
            this.#timers.clearTimer(this.#resizeTimeout);
            this.#resizeTimeout = null;
        }
        this.#resizeObserver?.disconnect();
        this.#resizeObserver = null;
        this.#timers.cleanup();
        try {
            this.#xterm.dispose();
        } catch (error) {
            const runtimeError = ensureError(error);
            warnTerminalError('PTY terminal disposal failed', runtimeError);
        }
    }

    #resolveRenderedFontSize(): number {
        return this.#baseFontSize * this.#textViewportScale.scale;
    }

    #applyRenderedFontSize(): void {
        this.#xterm.options.fontSize = this.#resolveRenderedFontSize();
        if (!this.#mounted) return;
        this.#fitAddon.fit();
        this.#session.sendResize();
    }

    readonly #handleTextViewportScaleChanged = (): void => {
        if (this.#disposed) return;
        this.#applyRenderedFontSize();
    };

    #setupResizeObserver(): void {
        this.#resizeObserver = new ResizeObserver(() => {
            if (this.#resizeTimeout) {
                this.#timers.clearTimer(this.#resizeTimeout);
            }
            this.#resizeTimeout = this.#timers.setTimeout(() => {
                this.#fitAddon.fit();
                this.#session.sendResize();
            }, 100);
        });
        this.#resizeObserver.observe(this.#config.container);
    }
}

export { PTYTerminalView };
export { TERMINAL_FONT_SIZE };
export type { PTYTerminalConfig };
