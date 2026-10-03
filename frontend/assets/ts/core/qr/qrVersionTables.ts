/* SoAI - QR symbol version capacities and layouts for error correction level M [frontend/assets/ts/core/qr/qrVersionTables.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireNonNull } from '@core/assertions.ts';

interface QrBlockLayout {
    readonly blockCount: number;
    readonly eccCodewordsPerBlock: number;
    readonly shortBlockCount: number;
    readonly shortBlockCodewords: number;
}

const QR_MIN_VERSION = 1;
const QR_MAX_VERSION = 40;
const QR_BYTE_MODE_INDICATOR_BITS = 4;
const QR_ECC_CODEWORDS_PER_BLOCK_M: readonly number[] = [10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26, 26, 26, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28];
const QR_ERROR_CORRECTION_BLOCKS_M: readonly number[] = [1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16, 17, 17, 18, 20, 21, 23, 25, 26, 28, 29, 31, 33, 35, 37, 38, 40, 43, 45, 47, 49];

const assertQrVersion = (version: number): void => {
    if (!Number.isInteger(version) || version < QR_MIN_VERSION || version > QR_MAX_VERSION) {
        throw new RangeError(`QR version ${version} is outside ${QR_MIN_VERSION}-${QR_MAX_VERSION}`);
    }
};

const qrSymbolSize = (version: number): number => {
    assertQrVersion(version);
    return version * 4 + 17;
};

const alignmentPatternCount = (version: number): number => (version === 1 ? 0 : Math.floor(version / 7) + 2);

const rawDataModuleCount = (version: number): number => {
    assertQrVersion(version);
    const alignmentCount = alignmentPatternCount(version);
    const alignmentModules = alignmentCount === 0 ? 0 : (25 * alignmentCount - 10) * alignmentCount - 55;
    const versionInformationModules = version >= 7 ? 36 : 0;
    return (16 * version + 128) * version + 64 - alignmentModules - versionInformationModules;
};

const blockLayout = (version: number): QrBlockLayout => {
    const totalCodewords = Math.floor(rawDataModuleCount(version) / 8);
    const blockCount = requireNonNull(QR_ERROR_CORRECTION_BLOCKS_M[version - 1], 'QR error correction block count');
    return {
        blockCount,
        eccCodewordsPerBlock: requireNonNull(QR_ECC_CODEWORDS_PER_BLOCK_M[version - 1], 'QR error correction codewords per block'),
        shortBlockCount: blockCount - (totalCodewords % blockCount),
        shortBlockCodewords: Math.floor(totalCodewords / blockCount)
    };
};

const dataCodewordCount = (version: number): number => {
    const layout = blockLayout(version);
    return Math.floor(rawDataModuleCount(version) / 8) - layout.eccCodewordsPerBlock * layout.blockCount;
};

const characterCountBits = (version: number): number => {
    assertQrVersion(version);
    return version <= 9 ? 8 : 16;
};

const byteModeCapacityM = (version: number): number => Math.floor((dataCodewordCount(version) * 8 - QR_BYTE_MODE_INDICATOR_BITS - characterCountBits(version)) / 8);

const selectVersionM = (byteLength: number): number => {
    for (let version = QR_MIN_VERSION; version <= QR_MAX_VERSION; version += 1) {
        if (byteLength <= byteModeCapacityM(version)) return version;
    }
    throw new RangeError(`QR payload of ${byteLength} bytes exceeds version ${QR_MAX_VERSION} capacity`);
};

const alignmentPositions = (version: number): readonly number[] => {
    const alignmentCount = alignmentPatternCount(version);
    if (alignmentCount === 0) return [];
    const size = qrSymbolSize(version);
    const step = version === 32 ? 26 : Math.ceil((version * 4 + 4) / (alignmentCount * 2 - 2)) * 2;
    const positions = [6];
    for (let position = size - 7; positions.length < alignmentCount; position -= step) {
        positions.splice(1, 0, position);
    }
    return positions;
};

export { alignmentPositions, blockLayout, byteModeCapacityM, characterCountBits, dataCodewordCount, qrSymbolSize, QR_BYTE_MODE_INDICATOR_BITS, rawDataModuleCount, selectVersionM };
export type { QrBlockLayout };
