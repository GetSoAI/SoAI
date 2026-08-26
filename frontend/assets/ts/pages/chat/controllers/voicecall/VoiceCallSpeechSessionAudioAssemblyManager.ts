/* SoAI - Voice call speech session audio assembly manager [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallSpeechSessionAudioAssemblyManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeBase64Bytes } from '@core/primitives/base64.ts';

interface VoiceCallSpeechSegmentAudioAssembly {
    nextChunkSequence: number;
    chunks: Uint8Array[];
}

const appendChunk = (assembly: VoiceCallSpeechSegmentAudioAssembly, chunkSequence: number, chunkBase64: string): boolean => {
    if (chunkSequence !== assembly.nextChunkSequence) {
        return false;
    }
    assembly.chunks.push(decodeBase64Bytes(chunkBase64));
    assembly.nextChunkSequence += 1;
    return true;
};

const concatenateChunks = (chunks: Uint8Array[]): Uint8Array => {
    let totalLength = 0;
    for (const chunk of chunks) {
        totalLength += chunk.byteLength;
    }
    const bytes = new Uint8Array(totalLength);
    let offset = 0;
    for (const chunk of chunks) {
        bytes.set(chunk, offset);
        offset += chunk.byteLength;
    }
    return bytes;
};

const createAssembly = (): VoiceCallSpeechSegmentAudioAssembly => ({
    nextChunkSequence: 0,
    chunks: []
});

const VoiceCallSpeechSessionAudioAssemblyManager = {
    appendChunk,
    concatenateChunks,
    createAssembly
};

export { VoiceCallSpeechSessionAudioAssemblyManager };
export type { VoiceCallSpeechSegmentAudioAssembly };
