/* SoAI - PTY terminal view support [frontend/assets/ts/features/terminal/PTYTerminalViewSupport.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';

const MODULE_ID = 'features.terminal.PTYTerminalView';
const PTY_CONNECT_HANDSHAKE_TIMEOUT_MS = 8000;
const TERMINAL_FONT_SIZE = { MIN: 8, MAX: 32, DEFAULT: 14 };
const debugTerminalError = <T>(message: string, error: T): void => {
    errorHandler.debug(MODULE_ID, message, ensureError(error));
};
const warnTerminalError = <T>(message: string, error: T): void => {
    errorHandler.warn(MODULE_ID, message, ensureError(error));
};
interface PTYTerminalConfig {
    container: HTMLElement;
    shell?: string;
    fontSize?: number;
    onSessionCreated?: (sessionId: string) => void;
    onSessionClosed?: (sessionId: string, exitCode?: number) => void;
    onError?: (error: string) => void;
    onBusyStateChanged?: (busy: boolean) => void;
}

export { MODULE_ID, PTY_CONNECT_HANDSHAKE_TIMEOUT_MS, TERMINAL_FONT_SIZE, debugTerminalError, warnTerminalError };
export type { PTYTerminalConfig };

class PTYTerminalConnectError extends Error {
    readonly code: string | null;

    constructor(message: string, code: string | null) {
        super(message);
        this.code = code;
    }
}

const isPTYTerminalConnectError = (value: Error): value is PTYTerminalConnectError => value instanceof PTYTerminalConnectError;

export { PTYTerminalConnectError, isPTYTerminalConnectError };
