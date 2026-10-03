/* SoAI - QR data masking and ISO 18004 mask penalty scoring [frontend/assets/ts/core/qr/qrMasking.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isDarkModule, isReservedModule, setModule, type QrGrid, type QrMaskId } from '@core/qr/qrFunctionPatterns.ts';

const QR_PENALTY_RUN = 3;
const QR_PENALTY_BLOCK = 3;
const QR_PENALTY_FINDER_LIKE = 40;
const QR_PENALTY_BALANCE = 10;
const QR_MIN_PENALIZED_RUN = 5;
const QR_FINDER_LIKE_PATTERN: readonly boolean[] = [true, false, true, true, true, false, true];
const QR_FINDER_LIKE_QUIET_LENGTH = 4;

const isMaskedPosition = (mask: QrMaskId, row: number, column: number): boolean => {
    const product = row * column;
    switch (mask) {
        case 0:
            return (row + column) % 2 === 0;
        case 1:
            return row % 2 === 0;
        case 2:
            return column % 3 === 0;
        case 3:
            return (row + column) % 3 === 0;
        case 4:
            return (Math.floor(row / 2) + Math.floor(column / 3)) % 2 === 0;
        case 5:
            return (product % 2) + (product % 3) === 0;
        case 6:
            return ((product % 2) + (product % 3)) % 2 === 0;
        case 7:
            return (((row + column) % 2) + (product % 3)) % 2 === 0;
    }
};

const applyMask = (grid: QrGrid, mask: QrMaskId): void => {
    for (let row = 0; row < grid.size; row += 1) {
        for (let column = 0; column < grid.size; column += 1) {
            if (isReservedModule(grid, row, column) || !isMaskedPosition(mask, row, column)) continue;
            setModule(grid, row, column, !isDarkModule(grid, row, column));
        }
    }
};

const isDarkAlongLine = (grid: QrGrid, horizontal: boolean, line: number, position: number): boolean => (horizontal ? isDarkModule(grid, line, position) : isDarkModule(grid, position, line));

const runPenalty = (runLength: number): number => (runLength >= QR_MIN_PENALIZED_RUN ? QR_PENALTY_RUN + runLength - QR_MIN_PENALIZED_RUN : 0);

const penaltyRuns = (grid: QrGrid): number => {
    let penalty = 0;
    for (const horizontal of [true, false]) {
        for (let line = 0; line < grid.size; line += 1) {
            let runLength = 0;
            let runDark = false;
            for (let position = 0; position < grid.size; position += 1) {
                const dark = isDarkAlongLine(grid, horizontal, line, position);
                if (position > 0 && dark === runDark) {
                    runLength += 1;
                    continue;
                }
                penalty += runPenalty(runLength);
                runLength = 1;
                runDark = dark;
            }
            penalty += runPenalty(runLength);
        }
    }
    return penalty;
};

const penaltyBlocks = (grid: QrGrid): number => {
    let blocks = 0;
    for (let row = 0; row < grid.size - 1; row += 1) {
        for (let column = 0; column < grid.size - 1; column += 1) {
            const dark = isDarkModule(grid, row, column);
            if (dark === isDarkModule(grid, row, column + 1) && dark === isDarkModule(grid, row + 1, column) && dark === isDarkModule(grid, row + 1, column + 1)) blocks += 1;
        }
    }
    return blocks * QR_PENALTY_BLOCK;
};

const isLightSpan = (grid: QrGrid, horizontal: boolean, line: number, start: number, end: number): boolean => {
    if (start < 0 || end > grid.size) return false;
    for (let position = start; position < end; position += 1) {
        if (isDarkAlongLine(grid, horizontal, line, position)) return false;
    }
    return true;
};

const matchesFinderLikePattern = (grid: QrGrid, horizontal: boolean, line: number, start: number): boolean => QR_FINDER_LIKE_PATTERN.every((dark, offset) => isDarkAlongLine(grid, horizontal, line, start + offset) === dark);

const penaltyFinderLike = (grid: QrGrid): number => {
    const patternLength = QR_FINDER_LIKE_PATTERN.length;
    let matches = 0;
    for (const horizontal of [true, false]) {
        for (let line = 0; line < grid.size; line += 1) {
            for (let start = 0; start + patternLength <= grid.size; start += 1) {
                if (!matchesFinderLikePattern(grid, horizontal, line, start)) continue;
                const end = start + patternLength;
                if (isLightSpan(grid, horizontal, line, start - QR_FINDER_LIKE_QUIET_LENGTH, start) || isLightSpan(grid, horizontal, line, end, end + QR_FINDER_LIKE_QUIET_LENGTH)) matches += 1;
            }
        }
    }
    return matches * QR_PENALTY_FINDER_LIKE;
};

const penaltyBalance = (grid: QrGrid): number => {
    const total = grid.size * grid.size;
    const dark = grid.modules.reduce((count, module) => count + module, 0);
    return Math.floor((Math.abs(dark * 2 - total) * 10) / total) * QR_PENALTY_BALANCE;
};

const maskPenalty = (grid: QrGrid): number => penaltyRuns(grid) + penaltyBlocks(grid) + penaltyFinderLike(grid) + penaltyBalance(grid);

export { applyMask, maskPenalty, penaltyBalance, penaltyBlocks, penaltyFinderLike, penaltyRuns };
