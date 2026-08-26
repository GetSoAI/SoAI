/* SoAI - Shared primitives base64 [frontend/assets/ts/core/primitives/base64.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const decodeBase64Utf8 = (value: string): string => {
    const binaryString = atob(value);
    const bytes = new Uint8Array(binaryString.length);
    for (let index = 0; index < binaryString.length; index += 1) {
        bytes[index] = binaryString.charCodeAt(index);
    }
    return new TextDecoder('utf-8').decode(bytes);
};

const decodeBase64Bytes = (value: string): Uint8Array => {
    const binaryString = atob(value);
    const bytes = new Uint8Array(binaryString.length);
    for (let index = 0; index < binaryString.length; index += 1) {
        bytes[index] = binaryString.charCodeAt(index);
    }
    return bytes;
};

const encodeBase64Bytes = (bytes: Uint8Array): string => {
    const chunkSize = 32_768;
    let binaryString = '';
    for (let offset = 0; offset < bytes.length; offset += chunkSize) {
        const slice = bytes.subarray(offset, Math.min(offset + chunkSize, bytes.length));
        let chunk = '';
        for (let index = 0; index < slice.length; index += 1) {
            const byte = slice[index];
            if (byte === undefined) {
                throw new Error('Invalid byte while encoding base64');
            }
            chunk += String.fromCharCode(byte);
        }
        binaryString += chunk;
    }
    return btoa(binaryString);
};

export { decodeBase64Bytes, decodeBase64Utf8, encodeBase64Bytes };
