/* SoAI - Frontend terminal PTY status writer [frontend/assets/ts/features/terminal/ptyTerminalStatusWriter.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { Terminal } from '@xterm/xterm';
import { i18n } from '@core/i18n/index.ts';

const writeDimStatus = (terminal: Terminal, message: string): void => {
    terminal.writeln('\r\n\x1b[90m[' + message + ']\x1b[0m');
};

const writeWarningStatus = (terminal: Terminal, message: string): void => {
    terminal.writeln('\r\n\x1b[33m[' + message + ']\x1b[0m');
};

const writeErrorStatus = (terminal: Terminal, message: string): void => {
    terminal.writeln('\r\n\x1b[31m' + message + '\x1b[0m');
};

const writePtyProcessExited = (terminal: Terminal, exitCodeText: string): void => {
    writeDimStatus(terminal, i18n.t('terminal.status.processExited', { code: exitCodeText }));
};

const writePtyError = (terminal: Terminal, message: string): void => {
    writeErrorStatus(terminal, i18n.t('terminal.status.error', { message }));
};

const writePtyConnectionLost = (terminal: Terminal): void => {
    writeErrorStatus(terminal, '[' + i18n.t('terminal.status.connectionLost') + ']');
};

const writePtyReconnecting = (terminal: Terminal): void => {
    writeWarningStatus(terminal, i18n.t('terminal.status.reconnecting'));
};

const writePtyReconnectionFailed = (terminal: Terminal): void => {
    writeErrorStatus(terminal, '[' + i18n.t('terminal.status.reconnectionFailed') + ']');
};

export { writePtyConnectionLost, writePtyError, writePtyProcessExited, writePtyReconnecting, writePtyReconnectionFailed };
