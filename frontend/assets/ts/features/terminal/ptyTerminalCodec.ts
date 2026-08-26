/* SoAI - PTY terminal codec [frontend/assets/ts/features/terminal/ptyTerminalCodec.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeBase64Bytes, encodeBase64Bytes } from '@core/primitives/base64.ts';

const encodeTerminalInput = (value: string): string => {
    return encodeBase64Bytes(new TextEncoder().encode(value));
};

const decodeTerminalOutput = (encodedData: string): Uint8Array => {
    return decodeBase64Bytes(encodedData);
};

export { decodeTerminalOutput, encodeTerminalInput };
