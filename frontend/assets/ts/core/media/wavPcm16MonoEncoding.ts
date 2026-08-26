/* SoAI - WAV PCM16 mono encoding [frontend/assets/ts/core/media/wavPcm16MonoEncoding.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNumber } from '@core/typeGuards.ts';

const clampFloatSample = (sample: number): number => Math.max(-1, Math.min(1, sample));

const writeAscii = (view: DataView, offset: number, value: string): void => {
    for (let index = 0; index < value.length; index += 1) {
        view.setUint8(offset + index, value.charCodeAt(index) & 0xff);
    }
};

const encodeWavPcm16Mono = (frames: Float32Array[], sampleRate: number): Blob => {
    const rate = isNumber(sampleRate) && Number.isFinite(sampleRate) && sampleRate > 0 ? Math.floor(sampleRate) : 48_000;
    let sampleCount = 0;
    for (const frame of frames) {
        sampleCount += frame.length;
    }
    if (sampleCount < 1) {
        return new Blob([], { type: 'audio/wav' });
    }

    const bytesPerSample = 2;
    const dataSize = sampleCount * bytesPerSample;
    const buffer = new ArrayBuffer(44 + dataSize);
    const view = new DataView(buffer);
    const numberChannels = 1;
    const blockAlign = numberChannels * bytesPerSample;
    const byteRate = rate * blockAlign;

    writeAscii(view, 0, 'RIFF');
    view.setUint32(4, 36 + dataSize, true);
    writeAscii(view, 8, 'WAVE');
    writeAscii(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, numberChannels, true);
    view.setUint32(24, rate, true);
    view.setUint32(28, byteRate, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, 16, true);
    writeAscii(view, 36, 'data');
    view.setUint32(40, dataSize, true);

    let writeOffset = 44;
    for (const frame of frames) {
        for (let index = 0; index < frame.length; index += 1) {
            const clamped = clampFloatSample(frame[index] ?? 0);
            const intValue = clamped < 0 ? Math.round(clamped * 0x8000) : Math.round(clamped * 0x7fff);
            view.setInt16(writeOffset, intValue, true);
            writeOffset += 2;
        }
    }

    return new Blob([buffer], { type: 'audio/wav' });
};

export { encodeWavPcm16Mono };
