/* SoAI - PTY terminal disconnect queue [frontend/assets/ts/features/terminal/ptyTerminalDisconnectQueue.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { sendPtyDisconnectMessage } from '@features/terminal/ptyTerminalTransport.ts';
import { warnTerminalError } from '@features/terminal/PTYTerminalViewSupport.ts';

let pendingDisconnect: Promise<void> | null = null;

const queuePtyDisconnect = (): void => {
    const previousDisconnect = pendingDisconnect;
    const disconnect = (async (): Promise<void> => {
        if (previousDisconnect) {
            await previousDisconnect;
        }
        await sendPtyDisconnectMessage();
    })().catch((error) => {
        warnTerminalError('PTY disconnect failed', error);
    });
    pendingDisconnect = disconnect;
};

const settlePendingPtyDisconnects = async (): Promise<void> => {
    while (pendingDisconnect) {
        const disconnect = pendingDisconnect;
        await disconnect;
        if (pendingDisconnect === disconnect) {
            pendingDisconnect = null;
        }
    }
};

export { queuePtyDisconnect, settlePendingPtyDisconnects };
