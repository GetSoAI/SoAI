/* SoAI - PTY terminal session [frontend/assets/ts/features/terminal/ptyTerminalSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { FitAddon } from '@xterm/addon-fit';
import { Terminal } from '@xterm/xterm';
import { ensureError } from '@core/errors/coerce.ts';
import { raceWithAbortSignal, throwIfAborted } from '@core/errors/abort.ts';
import { i18n } from '@core/i18n/index.ts';
import type { PtyBusyEvent, PtyConnectedEvent, PtyDisconnectedEvent, PtyErrorEvent, PtyExitedEvent, PtyOutputEvent } from '@core/realtime/eventcontracts/terminalContracts.ts';
import { connectWebSocket, waitForWebSocketConnection } from '@core/websocketclient/service.ts';
import { decodeTerminalOutput } from '@features/terminal/ptyTerminalCodec.ts';
import { PtyConnectHandshake } from '@features/terminal/ptyConnectHandshake.ts';
import { PtyTerminalEventBuffer } from '@features/terminal/ptyTerminalEventBuffer.ts';
import { sendPtyConnectMessage, sendPtyInputMessage, sendPtyResizeMessage } from '@features/terminal/ptyTerminalTransport.ts';
import { queuePtyDisconnect, settlePendingPtyDisconnects } from '@features/terminal/ptyTerminalDisconnectQueue.ts';
import { PTY_CONNECT_HANDSHAKE_TIMEOUT_MS, debugTerminalError, warnTerminalError, type PTYTerminalConfig } from '@features/terminal/PTYTerminalViewSupport.ts';
import { subscribePtyTerminalSessionEvents } from '@features/terminal/ptyTerminalSessionSubscriptions.ts';
import { writePtyConnectionLost, writePtyError, writePtyProcessExited, writePtyReconnecting, writePtyReconnectionFailed } from '@features/terminal/ptyTerminalStatusWriter.ts';

class PtyTerminalSession {
    readonly #terminal: Terminal;
    readonly #fitAddon: FitAddon;
    readonly #config: PTYTerminalConfig;
    readonly #connectHandshake: PtyConnectHandshake = new PtyConnectHandshake();
    readonly #eventBuffer: PtyTerminalEventBuffer = new PtyTerminalEventBuffer();
    #sessionId: string | null = null;
    #busy: boolean = false;
    #connectTask: Promise<void> | null = null;
    #initialConnectDone: boolean = false;
    #disposed: boolean = false;
    #connectGeneration: number = 0;
    #unsubscribers: Array<() => void> = [];

    constructor(options: { terminal: Terminal; fitAddon: FitAddon; config: PTYTerminalConfig }) {
        this.#terminal = options.terminal;
        this.#fitAddon = options.fitAddon;
        this.#config = options.config;
    }

    get busy(): boolean {
        return this.#busy;
    }

    initialize(): void {
        if (this.#disposed) return;
        this.#setupWebSocketSubscriptions();
        this.#setupInputHandler();
    }

    async connect(signal?: AbortSignal): Promise<void> {
        if (this.#disposed) return;
        await this.#connect(signal);
        throwIfAborted(signal);
        this.#initialConnectDone = true;
    }

    sendResize(): void {
        if (this.#disposed) return;
        if (!this.#sessionId) return;
        const dims = this.#fitAddon.proposeDimensions();
        if (!dims) return;
        sendPtyResizeMessage(dims.cols, dims.rows).catch((error) => {
            debugTerminalError('Failed to send resize', error);
        });
    }

    clear(): void {
        if (this.#disposed) return;
        this.#terminal.reset();
    }

    dispose(): void {
        if (this.#disposed) return;
        this.#disposed = true;
        this.#connectHandshake.dispose();

        if (this.#sessionId) {
            queuePtyDisconnect();
        }

        for (const unsubscribe of this.#unsubscribers) {
            try {
                unsubscribe();
            } catch (error) {
                const runtimeError = ensureError(error);
                warnTerminalError('PTY subscription cleanup failed', runtimeError);
            }
        }
        this.#unsubscribers = [];
        this.#sessionId = null;
        this.#busy = false;
        this.#connectGeneration += 1;
        this.#eventBuffer.clear();
    }

    #setupWebSocketSubscriptions(): void {
        this.#unsubscribers.push(
            subscribePtyTerminalSessionEvents({
                onConnected: (payload: PtyConnectedEvent): void => this.#handleConnected(payload),
                onOutput: (payload: PtyOutputEvent): void => this.#handleOutput(payload),
                onExited: (payload: PtyExitedEvent): void => this.#handleExited(payload),
                onDisconnected: (payload: PtyDisconnectedEvent): void => this.#handleDisconnected(payload),
                onError: (payload: PtyErrorEvent): void => this.#handleError(payload),
                onBusy: (payload: PtyBusyEvent): void => this.#handleBusy(payload),
                onWebSocketDisconnected: () => this.#handleWsDisconnected(),
                onWebSocketConnected: () => this.#handleWsReconnected()
            })
        );
    }

    #setupInputHandler(): void {
        this.#terminal.onData((data: string) => {
            if (this.#disposed) return;
            if (!this.#sessionId) return;
            sendPtyInputMessage(data).catch((error) => {
                debugTerminalError('Failed to send PTY input', error);
            });
        });
    }

    async #connect(signal?: AbortSignal): Promise<void> {
        throwIfAborted(signal);
        const activeTask = this.#connectTask;
        if (activeTask) {
            await (signal ? raceWithAbortSignal(activeTask, signal) : activeTask);
            return;
        }
        if (this.#sessionId) {
            return;
        }

        const task = this.#performConnect(signal);
        this.#connectTask = task;
        try {
            await task;
        } finally {
            if (this.#connectTask === task) {
                this.#connectTask = null;
            }
        }
    }

    async #performConnect(signal?: AbortSignal): Promise<void> {
        await settlePendingPtyDisconnects();
        throwIfAborted(signal);
        this.#connectGeneration += 1;
        const generation = this.#connectGeneration;
        this.#eventBuffer.start(generation);
        let connectMessageSent = false;
        try {
            connectWebSocket();
            await waitForWebSocketConnection(undefined, { signal });
            throwIfAborted(signal);
            const handshake = this.#connectHandshake.start(PTY_CONNECT_HANDSHAKE_TIMEOUT_MS);
            const dims = this.#fitAddon.proposeDimensions();
            await sendPtyConnectMessage(dims?.cols ?? 80, dims?.rows ?? 24, this.#config.shell ?? null, signal);
            connectMessageSent = true;
            await (signal ? raceWithAbortSignal(handshake.promise, signal) : handshake.promise);
        } catch (error) {
            if (connectMessageSent) {
                queuePtyDisconnect();
            }
            throw error;
        } finally {
            if (!this.#sessionId) {
                this.#eventBuffer.clear();
            }
            this.#connectHandshake.clear();
        }
    }

    #handleConnected(payload: PtyConnectedEvent): void {
        this.#sessionId = payload.sessionId;
        this.#connectHandshake.resolve(payload.sessionId);
        this.#config.onSessionCreated?.(payload.sessionId);
        this.#flushBufferedEvents(payload.sessionId);
        this.#terminal.focus();
    }

    #handleOutput(payload: PtyOutputEvent): void {
        if (payload.sessionId !== this.#sessionId) {
            this.#bufferPendingEvent({ type: 'output', payload });
            return;
        }
        try {
            this.#terminal.write(decodeTerminalOutput(payload.data));
        } catch (error) {
            const runtimeError = ensureError(error);
            debugTerminalError('Failed to decode PTY output', runtimeError);
        }
    }

    #handleExited(payload: PtyExitedEvent): void {
        if (payload.sessionId !== this.#sessionId) {
            this.#bufferPendingEvent({ type: 'exited', payload });
            return;
        }
        this.#sessionId = null;
        if (this.#busy) {
            this.#busy = false;
            this.#config.onBusyStateChanged?.(false);
        }
        writePtyProcessExited(this.#terminal, String(payload.exitCode));
        this.#config.onSessionClosed?.(payload.sessionId, payload.exitCode);
    }

    #handleDisconnected(payload: PtyDisconnectedEvent): void {
        if (payload.sessionId !== this.#sessionId) return;
        this.#sessionId = null;
    }

    #handleError(payload: PtyErrorEvent): void {
        const errorMessage = payload.message || i18n.t('terminal.status.unknownError');
        if (!this.#sessionId) {
            this.#connectHandshake.reject(errorMessage, String(payload.code));
            this.#eventBuffer.clear();
        }
        writePtyError(this.#terminal, errorMessage);
        this.#config.onError?.(errorMessage);
    }

    #handleWsDisconnected(): void {
        if (!this.#sessionId) {
            return;
        }
        this.#eventBuffer.clear();
        writePtyConnectionLost(this.#terminal);
        this.#sessionId = null;
        if (this.#busy) {
            this.#busy = false;
            this.#config.onBusyStateChanged?.(false);
        }
    }

    #handleWsReconnected(): void {
        if (this.#disposed) return;
        if (!this.#initialConnectDone) return;
        if (this.#sessionId) return;
        writePtyReconnecting(this.#terminal);
        this.#connect().catch((error) => {
            if (this.#disposed) return;
            warnTerminalError('Reconnection failed', error);
            writePtyReconnectionFailed(this.#terminal);
        });
    }

    #handleBusy(payload: PtyBusyEvent): void {
        if (payload.sessionId !== this.#sessionId) {
            this.#bufferPendingEvent({ type: 'busy', payload });
            return;
        }
        if (this.#busy !== payload.busy) {
            this.#busy = payload.busy;
            this.#config.onBusyStateChanged?.(payload.busy);
        }
    }

    #bufferPendingEvent(event: { type: 'output'; payload: PtyOutputEvent } | { type: 'exited'; payload: PtyExitedEvent } | { type: 'busy'; payload: PtyBusyEvent }): void {
        if (!this.#connectTask || this.#sessionId) return;
        this.#eventBuffer.push(event, this.#connectGeneration);
    }

    #flushBufferedEvents(sessionId: string): void {
        this.#eventBuffer.drainForSession(sessionId, this.#connectGeneration, {
            onOutput: (payload: PtyOutputEvent): void => this.#handleOutput(payload),
            onExited: (payload: PtyExitedEvent): void => this.#handleExited(payload),
            onBusy: (payload: PtyBusyEvent): void => this.#handleBusy(payload)
        });
    }
}

export { PtyTerminalSession };
