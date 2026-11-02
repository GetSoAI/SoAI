/* SoAI - PTY terminal session [frontend/assets/ts/features/terminal/ptyTerminalSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { FitAddon } from '@xterm/addon-fit';
import { Terminal } from '@xterm/xterm';
import { ensureError } from '@core/errors/coerce.ts';
import { createAbortError, raceWithAbortSignal, runWithAbortSignalScope, throwIfAborted } from '@core/errors/abort.ts';
import { getAuthManager } from '@core/auth/public.ts';
import { createMutationRequestId } from '@core/mutations/mutationIdentity.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { runAsyncCleanupStepCollectingFailure, runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';
import { i18n } from '@core/i18n/index.ts';
import type { PtyBusyEvent, PtyConnectedEvent, PtyDisconnectedEvent, PtyErrorEvent, PtyExitedEvent, PtyOutputEvent } from '@core/realtime/eventcontracts/terminalContracts.ts';
import { connectWebSocket, getWebSocketClient, isCurrentWebSocketClient, waitForWebSocketConnection } from '@core/websocketclient/service.ts';
import type { WebSocketDispatchContext } from '@core/websocketclient/types.ts';
import { isAvailableFocusTarget } from '@core/dom/focusTarget.ts';
import { isPositiveInteger } from '@core/typeGuards.ts';
import { decodeTerminalOutput } from '@features/terminal/ptyTerminalCodec.ts';
import { PtyConnectHandshake } from '@features/terminal/ptyConnectHandshake.ts';
import { PtyTerminalEventBuffer } from '@features/terminal/ptyTerminalEventBuffer.ts';
import { sendPtyConnectMessage, sendPtyInputMessage, sendPtyResizeMessage, waitForPtyRuntime, type PtyTerminalAcquisition } from '@features/terminal/ptyTerminalTransport.ts';
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
    #connection: PtyTerminalAcquisition | null = null;
    readonly #lifetime = new AbortController();
    #disposal: Promise<void> | null = null;
    #processExited = false;

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
        this.#config.owner.admission.requireActive();
        this.#setupWebSocketSubscriptions();
        this.#setupInputHandler();
    }

    async connect(signal?: AbortSignal): Promise<void> {
        if (this.#disposed) throw createAbortError('PTY session is disposed');
        await this.#connect(signal);
        throwIfAborted(signal);
        if (this.#disposed) throw createAbortError('PTY session was retired during connection');
        this.#config.owner.admission.requireActive();
        this.#initialConnectDone = true;
    }

    sendResize(): void {
        if (this.#disposed) return;
        if (!this.#sessionId || this.#processExited || !this.#connection) return;
        if (!this.#config.owner.presentation.isVisible()) return;
        const dims = this.#fitAddon.proposeDimensions();
        if (!dims || !isPositiveInteger(dims.cols) || !isPositiveInteger(dims.rows)) return;
        sendPtyResizeMessage(this.#connection, dims.cols, dims.rows).catch((error) => {
            debugTerminalError('Failed to send resize', error);
        });
    }

    clear(): void {
        if (this.#disposed) return;
        this.#terminal.reset();
    }

    dispose(): Promise<void> {
        if (this.#disposal) return this.#disposal;
        const completion = createDeferred<void>();
        this.#disposal = completion.promise;
        this.#disposed = true;
        const failures: Error[] = [];
        const release = this.#connection ? queuePtyDisconnect(this.#connection) : Promise.resolve();
        this.#lifetime.abort();
        runCleanupStepCollectingFailure(() => this.#connectHandshake.dispose(), failures);
        for (const unsubscribe of [...this.#unsubscribers]) {
            runCleanupStepCollectingFailure(() => {
                unsubscribe();
                this.#unsubscribers.splice(this.#unsubscribers.indexOf(unsubscribe), 1);
            }, failures);
        }
        this.#busy = false;
        this.#connectGeneration += 1;
        this.#eventBuffer.clear();
        void runAsyncCleanupStepCollectingFailure(() => release, failures)
            .then(() => {
                throwCollectedCleanupFailures(failures);
                this.#connection = null;
                this.#sessionId = null;
            })
            .then(completion.resolve, (error) => completion.reject(ensureError(error)));
        return completion.promise;
    }

    #ownsConnection(context: WebSocketDispatchContext): boolean {
        const connection = this.#connection;
        return !this.#disposed && this.#config.owner.admission.isCurrent() && connection !== null && isCurrentWebSocketClient(connection.client) && connection.client.connectionEpoch === connection.connectionEpoch && context.connectionEpoch === connection.connectionEpoch;
    }

    #setupWebSocketSubscriptions(): void {
        const unsubscribe = subscribePtyTerminalSessionEvents({
            onConnected: (payload, context) => {
                if (this.#ownsConnection(context)) this.#handleConnected(payload);
            },
            onOutput: (payload, context) => {
                if (this.#ownsConnection(context)) this.#handleOutput(payload);
            },
            onExited: (payload, context) => {
                if (this.#ownsConnection(context)) this.#handleExited(payload);
            },
            onDisconnected: (payload, context) => {
                if (this.#ownsConnection(context)) this.#handleDisconnected(payload);
            },
            onError: (payload, context) => {
                if (this.#ownsConnection(context)) this.#handleError(payload);
            },
            onBusy: (payload, context) => {
                if (this.#ownsConnection(context)) this.#handleBusy(payload);
            },
            onWebSocketDisconnected: (context) => {
                if (this.#ownsConnection(context)) this.#handleWsDisconnected();
            },
            onWebSocketConnected: () => this.#handleWsReconnected()
        });
        if (this.#disposed) unsubscribe();
        else this.#unsubscribers.push(unsubscribe);
    }

    #setupInputHandler(): void {
        if (this.#disposed) return;
        const input = this.#terminal.onData((data: string) => {
            if (this.#disposed) return;
            if (!this.#config.owner.presentation.isFocused()) return;
            if (!this.#config.owner.admission.canMutate()) return;
            if (!this.#sessionId || this.#processExited || !this.#connection) return;
            sendPtyInputMessage(this.#connection, data).catch((error) => {
                debugTerminalError('Failed to send PTY input', error);
            });
        });
        if (this.#disposed) input.dispose();
        else this.#unsubscribers.push(() => input.dispose());
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

        const completion = createDeferred<void>();
        const task = completion.promise;
        this.#connectTask = task;
        void runWithAbortSignalScope([signal, this.#lifetime.signal], (connectionSignal) => this.#performConnect(connectionSignal)).then(completion.resolve, (error) => completion.reject(ensureError(error)));
        void task.then(
            () => {
                if (this.#connectTask === task) this.#connectTask = null;
            },
            () => {
                if (this.#connectTask === task) this.#connectTask = null;
            }
        );
        await (signal ? raceWithAbortSignal(task, signal) : task);
    }

    async #performConnect(signal?: AbortSignal): Promise<void> {
        if (this.#connection && !this.#sessionId) {
            void queuePtyDisconnect(this.#connection).catch((error) => warnTerminalError('PTY acquisition release failed', error));
        }
        await settlePendingPtyDisconnects();
        throwIfAborted(signal);
        if (this.#disposed) throw createAbortError('PTY connection acquisition is sealed');
        this.#config.owner.admission.requireActive();
        this.#connectGeneration += 1;
        this.#eventBuffer.start(this.#connectGeneration);
        try {
            connectWebSocket();
            await waitForWebSocketConnection(undefined, { signal });
            throwIfAborted(signal);
            if (this.#disposed) throw createAbortError('PTY connection acquisition is sealed');
            this.#config.owner.admission.requireActive();
            const dims = this.#fitAddon.proposeDimensions();
            const dimensions = dims && isPositiveInteger(dims.cols) && isPositiveInteger(dims.rows) ? dims : this.#terminal;
            const client = getWebSocketClient();
            const transport = Object.freeze({ client, connectionEpoch: client.connectionEpoch });
            const runtimeId = await waitForPtyRuntime(transport, signal);
            throwIfAborted(signal);
            if (this.#disposed) throw createAbortError('PTY connection acquisition is sealed');
            this.#config.owner.admission.requireActive();
            const connection = Object.freeze({ ...transport, runtimeId, acquisitionId: createMutationRequestId(), authEpoch: getAuthManager().authEpoch });
            this.#connection = connection;
            this.#processExited = false;
            const command = createDeferred<void>();
            const handshake = this.#connectHandshake.start(PTY_CONNECT_HANDSHAKE_TIMEOUT_MS);
            const connecting = Promise.all([command.promise, handshake.promise]);
            void sendPtyConnectMessage(connection, dimensions.cols, dimensions.rows, this.#config.shell ?? null, signal).then(command.resolve, (error) => command.reject(ensureError(error)));
            await connecting;
        } finally {
            if (!this.#sessionId) {
                this.#eventBuffer.clear();
            }
            this.#connectHandshake.clear();
        }
    }

    #handleConnected(payload: PtyConnectedEvent): void {
        if (this.#sessionId !== null || this.#disposed || payload.identity?.acquisitionId !== this.#connection?.acquisitionId || payload.identity?.runtimeId !== this.#connection?.runtimeId) return;
        this.#sessionId = payload.sessionId;
        this.#connectHandshake.resolve(payload.sessionId);
        this.#config.onSessionCreated?.(payload.sessionId);
        this.#flushBufferedEvents(payload.sessionId);
        if (!this.#disposed && this.#config.owner.presentation.isFocused() && this.#config.container.isConnected && isAvailableFocusTarget(this.#config.container)) this.#terminal.focus();
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
        this.#processExited = true;
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
        const acquisitionId = payload.details?.['acquisition_id'];
        const runtimeId = payload.details?.['runtime_id'];
        if ((!this.#sessionId || acquisitionId !== undefined || runtimeId !== undefined) && (acquisitionId !== this.#connection?.acquisitionId || runtimeId !== this.#connection?.runtimeId)) return;
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
    }

    #handleWsReconnected(): void {
        if (this.#disposed) return;
        if (!this.#initialConnectDone) return;
        if (this.#connection && (!isCurrentWebSocketClient(this.#connection.client) || this.#connection.client.connectionEpoch !== this.#connection.connectionEpoch)) {
            writePtyReconnectionFailed(this.#terminal);
            return;
        }
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
