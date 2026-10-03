/* SoAI - QR byte-mode encoder at error correction level M [frontend/assets/ts/core/qr/qrEncoder.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildDataCodewords, interleaveBlocks, placeCodewords } from '@core/qr/qrDataEncoding.ts';
import { createQrGrid, drawFormatInformation, QR_MASK_IDS, type QrGrid, type QrMaskId } from '@core/qr/qrFunctionPatterns.ts';
import { applyMask, maskPenalty } from '@core/qr/qrMasking.ts';
import { selectVersionM } from '@core/qr/qrVersionTables.ts';

interface QrMatrix {
    readonly version: number;
    readonly mask: QrMaskId;
    readonly size: number;
    readonly modules: Uint8Array;
}

interface QrEncodeOptions {
    readonly forceMask?: QrMaskId;
}

const buildMaskedGrid = (unmasked: QrGrid, mask: QrMaskId): QrGrid => {
    const grid: QrGrid = { version: unmasked.version, size: unmasked.size, modules: unmasked.modules.slice(), reserved: unmasked.reserved.slice() };
    applyMask(grid, mask);
    drawFormatInformation(grid, mask);
    return grid;
};

const chooseMaskedGrid = (unmasked: QrGrid): { readonly mask: QrMaskId; readonly grid: QrGrid } => {
    let best: { readonly mask: QrMaskId; readonly grid: QrGrid; readonly penalty: number } | null = null;
    for (const mask of QR_MASK_IDS) {
        const grid = buildMaskedGrid(unmasked, mask);
        const penalty = maskPenalty(grid);
        if (best === null || penalty < best.penalty) best = { mask, grid, penalty };
    }
    if (best === null) throw new Error('QR mask selection requires at least one mask');
    return best;
};

const encodeQrByteModeM = (payload: Uint8Array, options: QrEncodeOptions = {}): QrMatrix => {
    const version = selectVersionM(payload.length);
    const unmasked = createQrGrid(version);
    placeCodewords(unmasked, interleaveBlocks(buildDataCodewords(payload, version), version));
    const { mask, grid } = options.forceMask === undefined ? chooseMaskedGrid(unmasked) : { mask: options.forceMask, grid: buildMaskedGrid(unmasked, options.forceMask) };
    return { version, mask, size: grid.size, modules: grid.modules };
};

export { encodeQrByteModeM };
export type { QrEncodeOptions, QrMatrix };
