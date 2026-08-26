/* SoAI - Chat feature image mime sniffer [frontend/assets/ts/features/chat/imageMimeSniffer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import { isImageMimeType } from '@core/media/mimeTypes.ts';
import { wallClockMs } from '@core/time/clock.ts';

type DetectedImageMimeType = 'image/jpeg' | 'image/png' | 'image/gif' | 'image/webp' | 'image/bmp' | 'image/heic' | 'image/heif' | 'image/avif' | 'image/tiff';

const readFileHeader = async (file: File, length: number): Promise<Uint8Array> => {
    const resolvedLength = Number.isFinite(length) ? Math.max(1, Math.trunc(length)) : 32;
    const slice = file.slice(0, resolvedLength);
    const buffer = await slice.arrayBuffer();
    return new Uint8Array(buffer);
};

const startsWithBytes = (bytes: Uint8Array, prefix: readonly number[]): boolean => {
    if (bytes.length < prefix.length) {
        return false;
    }
    for (let index = 0; index < prefix.length; index += 1) {
        if (bytes[index] !== prefix[index]) {
            return false;
        }
    }
    return true;
};

const startsWithAscii = (bytes: Uint8Array, text: string): boolean => {
    if (!isString(text) || !text) {
        return false;
    }
    if (bytes.length < text.length) {
        return false;
    }
    for (let index = 0; index < text.length; index += 1) {
        if (bytes[index] !== text.charCodeAt(index)) {
            return false;
        }
    }
    return true;
};

const readAsciiAtOffset = (bytes: Uint8Array, offset: number, length: number): string | null => {
    if (!Number.isFinite(offset) || !Number.isFinite(length)) {
        return null;
    }
    const start = Math.trunc(offset);
    const count = Math.trunc(length);
    if (start < 0 || count <= 0) {
        return null;
    }
    if (bytes.length < start + count) {
        return null;
    }
    let text = '';
    for (let index = 0; index < count; index += 1) {
        text += String.fromCharCode(bytes[start + index] ?? 0);
    }
    return text;
};

const matchesWebpSignature = (bytes: Uint8Array): boolean => {
    if (bytes.length < 12) {
        return false;
    }
    if (!startsWithAscii(bytes, 'RIFF')) {
        return false;
    }
    return bytes[8] === 0x57 && bytes[9] === 0x45 && bytes[10] === 0x42 && bytes[11] === 0x50;
};

const detectIsoBmffImageMimeType = (bytes: Uint8Array): DetectedImageMimeType | null => {
    if (bytes.length < 12) {
        return null;
    }
    const boxType = readAsciiAtOffset(bytes, 4, 4);
    if (boxType !== 'ftyp') {
        return null;
    }
    const majorBrand = readAsciiAtOffset(bytes, 8, 4);
    if (!majorBrand) {
        return null;
    }
    if (majorBrand === 'avif' || majorBrand === 'avis') {
        return 'image/avif';
    }
    if (majorBrand === 'heic' || majorBrand === 'heix' || majorBrand === 'hevc' || majorBrand === 'hev1') {
        return 'image/heic';
    }
    if (majorBrand === 'heif' || majorBrand === 'mif1' || majorBrand === 'msf1') {
        return 'image/heif';
    }
    return null;
};

const detectTiffMimeType = (bytes: Uint8Array): DetectedImageMimeType | null => {
    if (bytes.length < 4) {
        return null;
    }
    if (bytes[0] === 0x49 && bytes[1] === 0x49 && (bytes[2] === 0x2a || bytes[2] === 0x2b) && bytes[3] === 0x00) {
        return 'image/tiff';
    }
    if (bytes[0] === 0x4d && bytes[1] === 0x4d && bytes[2] === 0x00 && (bytes[3] === 0x2a || bytes[3] === 0x2b)) {
        return 'image/tiff';
    }
    return null;
};

const detectImageMimeTypeFromHeader = (bytes: Uint8Array): DetectedImageMimeType | null => {
    if (startsWithBytes(bytes, [0xff, 0xd8, 0xff])) {
        return 'image/jpeg';
    }
    if (startsWithBytes(bytes, [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])) {
        return 'image/png';
    }
    if (startsWithAscii(bytes, 'GIF87a') || startsWithAscii(bytes, 'GIF89a')) {
        return 'image/gif';
    }
    if (matchesWebpSignature(bytes)) {
        return 'image/webp';
    }
    if (startsWithAscii(bytes, 'BM')) {
        return 'image/bmp';
    }
    const isoType = detectIsoBmffImageMimeType(bytes);
    if (isoType) {
        return isoType;
    }
    const tiffType = detectTiffMimeType(bytes);
    if (tiffType) {
        return tiffType;
    }
    return null;
};

const normalizeImageMimeTypeFromHeader = async (file: File): Promise<File | null> => {
    if (!(file instanceof File)) {
        throw new TypeError('Image normalization requires a File');
    }

    const typeValue = file.type;
    const trimmedType = isString(typeValue) ? typeValue.trim().toLowerCase() : '';
    if (isImageMimeType(trimmedType)) {
        return file;
    }

    const header = await readFileHeader(file, 32);
    const detected = detectImageMimeTypeFromHeader(header);
    if (!detected) {
        return null;
    }

    const lastModified = typeof file.lastModified === 'number' && Number.isFinite(file.lastModified) ? file.lastModified : wallClockMs();
    const name = isString(file.name) && file.name.trim() ? file.name : 'image';
    return new File([file], name, { type: detected, lastModified });
};

export { normalizeImageMimeTypeFromHeader };
export type { DetectedImageMimeType };
