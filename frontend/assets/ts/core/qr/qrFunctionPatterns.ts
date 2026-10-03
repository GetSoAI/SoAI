/* SoAI - QR module grid with finder, timing, alignment and format patterns [frontend/assets/ts/core/qr/qrFunctionPatterns.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireNonNull } from '@core/assertions.ts';
import { alignmentPositions, qrSymbolSize } from '@core/qr/qrVersionTables.ts';

type QrMaskId = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7;

interface QrGrid {
    readonly version: number;
    readonly size: number;
    readonly modules: Uint8Array;
    readonly reserved: Uint8Array;
}

const QR_MASK_IDS: readonly QrMaskId[] = [0, 1, 2, 3, 4, 5, 6, 7];
const QR_FORMAT_GENERATOR = 0x537;
const QR_FORMAT_MASK = 0x5412;
const QR_VERSION_GENERATOR = 0x1f25;
const QR_ERROR_CORRECTION_LEVEL_M_BITS = 0b00;

const moduleOffset = (grid: QrGrid, row: number, column: number): number => row * grid.size + column;

const isDarkModule = (grid: QrGrid, row: number, column: number): boolean => requireNonNull(grid.modules[moduleOffset(grid, row, column)], 'QR module') === 1;

const isReservedModule = (grid: QrGrid, row: number, column: number): boolean => requireNonNull(grid.reserved[moduleOffset(grid, row, column)], 'QR reserved module') === 1;

const setModule = (grid: QrGrid, row: number, column: number, dark: boolean): void => {
    grid.modules[moduleOffset(grid, row, column)] = dark ? 1 : 0;
};

const setFunctionModule = (grid: QrGrid, row: number, column: number, dark: boolean): void => {
    setModule(grid, row, column, dark);
    grid.reserved[moduleOffset(grid, row, column)] = 1;
};

const isBitSet = (value: number, bitIndex: number): boolean => ((value >>> bitIndex) & 1) === 1;

const formatInformationBitsM = (mask: QrMaskId): number => {
    const data = (QR_ERROR_CORRECTION_LEVEL_M_BITS << 3) | mask;
    let remainder = data;
    for (let step = 0; step < 10; step += 1) {
        remainder = (remainder << 1) ^ ((remainder >>> 9) * QR_FORMAT_GENERATOR);
    }
    return ((data << 10) | remainder) ^ QR_FORMAT_MASK;
};

const versionInformationBits = (version: number): number => {
    let remainder = version;
    for (let step = 0; step < 12; step += 1) {
        remainder = (remainder << 1) ^ ((remainder >>> 11) * QR_VERSION_GENERATOR);
    }
    return (version << 12) | remainder;
};

const drawFinderPattern = (grid: QrGrid, centerRow: number, centerColumn: number): void => {
    for (let rowOffset = -4; rowOffset <= 4; rowOffset += 1) {
        for (let columnOffset = -4; columnOffset <= 4; columnOffset += 1) {
            const row = centerRow + rowOffset;
            const column = centerColumn + columnOffset;
            if (row < 0 || row >= grid.size || column < 0 || column >= grid.size) continue;
            const ring = Math.max(Math.abs(rowOffset), Math.abs(columnOffset));
            setFunctionModule(grid, row, column, ring !== 2 && ring !== 4);
        }
    }
};

const drawAlignmentPattern = (grid: QrGrid, centerRow: number, centerColumn: number): void => {
    for (let rowOffset = -2; rowOffset <= 2; rowOffset += 1) {
        for (let columnOffset = -2; columnOffset <= 2; columnOffset += 1) {
            setFunctionModule(grid, centerRow + rowOffset, centerColumn + columnOffset, Math.max(Math.abs(rowOffset), Math.abs(columnOffset)) !== 1);
        }
    }
};

const drawFormatInformation = (grid: QrGrid, mask: QrMaskId): void => {
    const bits = formatInformationBitsM(mask);
    const size = grid.size;
    for (let bitIndex = 0; bitIndex <= 5; bitIndex += 1) setFunctionModule(grid, bitIndex, 8, isBitSet(bits, bitIndex));
    setFunctionModule(grid, 7, 8, isBitSet(bits, 6));
    setFunctionModule(grid, 8, 8, isBitSet(bits, 7));
    setFunctionModule(grid, 8, 7, isBitSet(bits, 8));
    for (let bitIndex = 9; bitIndex < 15; bitIndex += 1) setFunctionModule(grid, 8, 14 - bitIndex, isBitSet(bits, bitIndex));
    for (let bitIndex = 0; bitIndex < 8; bitIndex += 1) setFunctionModule(grid, 8, size - 1 - bitIndex, isBitSet(bits, bitIndex));
    for (let bitIndex = 8; bitIndex < 15; bitIndex += 1) setFunctionModule(grid, size - 15 + bitIndex, 8, isBitSet(bits, bitIndex));
    setFunctionModule(grid, size - 8, 8, true);
};

const drawVersionInformation = (grid: QrGrid): void => {
    if (grid.version < 7) return;
    const bits = versionInformationBits(grid.version);
    for (let bitIndex = 0; bitIndex < 18; bitIndex += 1) {
        const dark = isBitSet(bits, bitIndex);
        const longAxis = grid.size - 11 + (bitIndex % 3);
        const shortAxis = Math.floor(bitIndex / 3);
        setFunctionModule(grid, shortAxis, longAxis, dark);
        setFunctionModule(grid, longAxis, shortAxis, dark);
    }
};

const createQrGrid = (version: number): QrGrid => {
    const size = qrSymbolSize(version);
    const grid: QrGrid = { version, size, modules: new Uint8Array(size * size), reserved: new Uint8Array(size * size) };
    for (let position = 0; position < size; position += 1) {
        setFunctionModule(grid, 6, position, position % 2 === 0);
        setFunctionModule(grid, position, 6, position % 2 === 0);
    }
    drawFinderPattern(grid, 3, 3);
    drawFinderPattern(grid, 3, size - 4);
    drawFinderPattern(grid, size - 4, 3);
    const positions = alignmentPositions(version);
    const lastIndex = positions.length - 1;
    positions.forEach((rowPosition, rowIndex) => {
        positions.forEach((columnPosition, columnIndex) => {
            const overlapsFinder = (rowIndex === 0 && columnIndex === 0) || (rowIndex === 0 && columnIndex === lastIndex) || (rowIndex === lastIndex && columnIndex === 0);
            if (!overlapsFinder) drawAlignmentPattern(grid, rowPosition, columnPosition);
        });
    });
    drawFormatInformation(grid, 0);
    drawVersionInformation(grid);
    return grid;
};

export { createQrGrid, drawFormatInformation, formatInformationBitsM, isDarkModule, isReservedModule, QR_MASK_IDS, setModule, versionInformationBits };
export type { QrGrid, QrMaskId };
