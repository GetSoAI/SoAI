/* SoAI - QR byte-mode data codewords, block interleaving and module placement [frontend/assets/ts/core/qr/qrDataEncoding.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireNonNull } from '@core/assertions.ts';
import { isReservedModule, setModule, type QrGrid } from '@core/qr/qrFunctionPatterns.ts';
import { reedSolomonGenerator, reedSolomonRemainder } from '@core/qr/qrReedSolomon.ts';
import { blockLayout, characterCountBits, dataCodewordCount, QR_BYTE_MODE_INDICATOR_BITS } from '@core/qr/qrVersionTables.ts';

const QR_BYTE_MODE_INDICATOR = 0b0100;
const QR_MAX_TERMINATOR_BITS = 4;
const QR_PAD_BYTES: readonly number[] = [0xec, 0x11];
const QR_VERTICAL_TIMING_COLUMN = 6;

const appendBits = (bits: number[], value: number, length: number): void => {
    for (let bitIndex = length - 1; bitIndex >= 0; bitIndex -= 1) bits.push((value >>> bitIndex) & 1);
};

const buildDataCodewords = (payload: Uint8Array, version: number): Uint8Array => {
    const capacityBits = dataCodewordCount(version) * 8;
    const bits: number[] = [];
    appendBits(bits, QR_BYTE_MODE_INDICATOR, QR_BYTE_MODE_INDICATOR_BITS);
    appendBits(bits, payload.length, characterCountBits(version));
    for (const payloadByte of payload) appendBits(bits, payloadByte, 8);
    if (bits.length > capacityBits) throw new RangeError(`QR payload of ${payload.length} bytes does not fit version ${version}`);
    appendBits(bits, 0, Math.min(QR_MAX_TERMINATOR_BITS, capacityBits - bits.length));
    appendBits(bits, 0, (8 - (bits.length % 8)) % 8);
    const codewords = new Uint8Array(capacityBits / 8);
    bits.forEach((bit, bitIndex) => {
        const codewordIndex = Math.floor(bitIndex / 8);
        codewords[codewordIndex] = requireNonNull(codewords[codewordIndex], 'QR data codeword') | (bit << (7 - (bitIndex % 8)));
    });
    for (let padIndex = bits.length / 8; padIndex < codewords.length; padIndex += 1) {
        codewords[padIndex] = requireNonNull(QR_PAD_BYTES[(padIndex - bits.length / 8) % QR_PAD_BYTES.length], 'QR pad byte');
    }
    return codewords;
};

const interleaveBlocks = (dataCodewords: Uint8Array, version: number): Uint8Array => {
    const layout = blockLayout(version);
    const generator = reedSolomonGenerator(layout.eccCodewordsPerBlock);
    const shortDataLength = layout.shortBlockCodewords - layout.eccCodewordsPerBlock;
    const dataBlocks: Uint8Array[] = [];
    const eccBlocks: Uint8Array[] = [];
    let offset = 0;
    for (let blockIndex = 0; blockIndex < layout.blockCount; blockIndex += 1) {
        const dataLength = shortDataLength + (blockIndex < layout.shortBlockCount ? 0 : 1);
        const dataBlock = dataCodewords.subarray(offset, offset + dataLength);
        offset += dataLength;
        dataBlocks.push(dataBlock);
        eccBlocks.push(reedSolomonRemainder(dataBlock, generator));
    }
    if (offset !== dataCodewords.length) throw new RangeError(`QR data codeword count ${dataCodewords.length} does not match version ${version}`);
    const interleaved: number[] = [];
    for (let codewordIndex = 0; codewordIndex <= shortDataLength; codewordIndex += 1) {
        for (const dataBlock of dataBlocks) {
            if (codewordIndex < dataBlock.length) interleaved.push(requireNonNull(dataBlock[codewordIndex], 'QR interleaved data codeword'));
        }
    }
    for (let codewordIndex = 0; codewordIndex < layout.eccCodewordsPerBlock; codewordIndex += 1) {
        for (const eccBlock of eccBlocks) interleaved.push(requireNonNull(eccBlock[codewordIndex], 'QR interleaved error correction codeword'));
    }
    return Uint8Array.from(interleaved);
};

const placeCodewords = (grid: QrGrid, codewords: Uint8Array): void => {
    const totalBits = codewords.length * 8;
    let bitIndex = 0;
    for (let columnStart = grid.size - 1; columnStart >= 1; columnStart -= 2) {
        const pairColumn = columnStart <= QR_VERTICAL_TIMING_COLUMN ? columnStart - 1 : columnStart;
        const upward = ((pairColumn + 1) & 2) === 0;
        for (let step = 0; step < grid.size; step += 1) {
            const row = upward ? grid.size - 1 - step : step;
            for (let columnOffset = 0; columnOffset < 2; columnOffset += 1) {
                const column = pairColumn - columnOffset;
                if (isReservedModule(grid, row, column) || bitIndex >= totalBits) continue;
                const codeword = requireNonNull(codewords[bitIndex >>> 3], 'QR placed codeword');
                setModule(grid, row, column, ((codeword >>> (7 - (bitIndex & 7))) & 1) === 1);
                bitIndex += 1;
            }
        }
    }
    if (bitIndex !== totalBits) throw new RangeError(`QR placement consumed ${bitIndex} of ${totalBits} codeword bits`);
};

export { buildDataCodewords, interleaveBlocks, placeCodewords };
