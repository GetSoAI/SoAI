/* SoAI - Chat feature TTS text chunker [frontend/assets/ts/features/chat/tts/chatTtsTextChunker.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const splitTextForTts = (text: string, options: { chunkMaxChars: number }): string[] => {
    const normalized = text.trim();
    if (!normalized) {
        return [];
    }
    if (normalized.length <= options.chunkMaxChars) {
        return [normalized];
    }
    const chunks: string[] = [];
    let cursor = 0;
    while (cursor < normalized.length) {
        const remaining = normalized.length - cursor;
        if (remaining <= options.chunkMaxChars) {
            const tail = normalized.slice(cursor).trim();
            if (tail) {
                chunks.push(tail);
            }
            break;
        }
        const windowEnd = cursor + options.chunkMaxChars;
        const windowText = normalized.slice(cursor, windowEnd);
        let splitOffset = -1;
        for (let index = windowText.length - 1; index >= 0; index -= 1) {
            const current = windowText[index];
            if (current === '\n' || current === '.' || current === '!' || current === '?') {
                splitOffset = index + 1;
                break;
            }
        }
        if (splitOffset <= 0) {
            for (let index = windowText.length - 1; index >= 0; index -= 1) {
                const current = windowText[index];
                if (current === ' ' || current === '\t') {
                    splitOffset = index + 1;
                    break;
                }
            }
        }
        if (splitOffset <= 0) {
            splitOffset = windowText.length;
        }
        const segment = normalized.slice(cursor, cursor + splitOffset).trim();
        if (segment) {
            chunks.push(segment);
        }
        cursor += splitOffset;
        while (cursor < normalized.length && /\s/.test(normalized[cursor] ?? '')) {
            cursor += 1;
        }
    }
    return chunks;
};

export { splitTextForTts };
