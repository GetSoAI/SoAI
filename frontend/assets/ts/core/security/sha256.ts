/* SoAI - Portable SHA-256 content digests [frontend/assets/ts/core/security/sha256.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const ROUND_CONSTANTS = new Uint32Array([0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2]);

const readWord = (words: Uint32Array, index: number): number => {
    const value = words[index];
    if (value === undefined) throw new RangeError('SHA-256 word index is out of bounds');
    return value;
};

const rotateRight = (value: number, distance: number): number => (value >>> distance) | (value << (32 - distance));

const sha256Hex = (value: string): string => {
    const encoded = new TextEncoder().encode(value);
    const padded = new Uint8Array(Math.ceil((encoded.length + 9) / 64) * 64);
    padded.set(encoded);
    padded[encoded.length] = 0x80;
    const view = new DataView(padded.buffer);
    view.setUint32(padded.length - 8, Math.floor(encoded.length / 0x20000000));
    view.setUint32(padded.length - 4, (encoded.length * 8) >>> 0);
    const state = new Uint32Array([0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]);
    const schedule = new Uint32Array(64);
    for (let offset = 0; offset < padded.length; offset += 64) {
        for (let index = 0; index < 16; index += 1) schedule[index] = view.getUint32(offset + index * 4);
        for (let index = 16; index < 64; index += 1) {
            const earlier = readWord(schedule, index - 15);
            const later = readWord(schedule, index - 2);
            const firstSigma = rotateRight(earlier, 7) ^ rotateRight(earlier, 18) ^ (earlier >>> 3);
            const secondSigma = rotateRight(later, 17) ^ rotateRight(later, 19) ^ (later >>> 10);
            schedule[index] = (readWord(schedule, index - 16) + firstSigma + readWord(schedule, index - 7) + secondSigma) >>> 0;
        }
        let first = readWord(state, 0);
        let second = readWord(state, 1);
        let third = readWord(state, 2);
        let fourth = readWord(state, 3);
        let fifth = readWord(state, 4);
        let sixth = readWord(state, 5);
        let seventh = readWord(state, 6);
        let eighth = readWord(state, 7);
        for (let index = 0; index < 64; index += 1) {
            const firstSigma = rotateRight(first, 2) ^ rotateRight(first, 13) ^ rotateRight(first, 22);
            const secondSigma = rotateRight(fifth, 6) ^ rotateRight(fifth, 11) ^ rotateRight(fifth, 25);
            const choice = (fifth & sixth) ^ (~fifth & seventh);
            const majority = (first & second) ^ (first & third) ^ (second & third);
            const firstTemporary = (eighth + secondSigma + choice + readWord(ROUND_CONSTANTS, index) + readWord(schedule, index)) >>> 0;
            const secondTemporary = (firstSigma + majority) >>> 0;
            eighth = seventh;
            seventh = sixth;
            sixth = fifth;
            fifth = (fourth + firstTemporary) >>> 0;
            fourth = third;
            third = second;
            second = first;
            first = (firstTemporary + secondTemporary) >>> 0;
        }
        const blockState = [first, second, third, fourth, fifth, sixth, seventh, eighth];
        blockState.forEach((word, index) => {
            state[index] = (readWord(state, index) + word) >>> 0;
        });
    }
    return Array.from(state, (word) => word.toString(16).padStart(8, '0')).join('');
};

export { sha256Hex };
