/* SoAI - Chat composer SoAI link source projection [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/composerSoaiLinkResolutionManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { extractSoaiPathTokenTexts } from '@core/soailinks/codec.ts';
import { resolveSoaiPathDraftRecordTitle, resolveSoaiPathDraftRecordToken, type SoaiPathDraftRecord } from '@features/chat/public.ts';

type ProjectionSegment = Readonly<{ display: string; source: string; link: boolean; record: SoaiPathDraftRecord | null }>;

const displayedText = (segments: readonly ProjectionSegment[]): string => segments.map((segment) => segment.display).join('');
const sourceText = (segments: readonly ProjectionSegment[]): string => segments.map((segment) => segment.source).join('');

const buildResolvedProjection = (currentSegments: readonly ProjectionSegment[], rawValue: string, records: readonly SoaiPathDraftRecord[]): ProjectionSegment[] => {
    const sourceSegments: readonly ProjectionSegment[] = displayedText(currentSegments) === rawValue ? currentSegments : rawValue ? [{ display: rawValue, source: rawValue, link: false, record: null }] : [];
    const segments: ProjectionSegment[] = [];
    let recordIndex = 0;
    for (const currentSegment of sourceSegments) {
        if (currentSegment.link) {
            segments.push(currentSegment);
            continue;
        }
        const tokens = extractSoaiPathTokenTexts(currentSegment.display);
        let cursor = 0;
        for (const token of tokens) {
            const record = records[recordIndex];
            if (record === undefined || resolveSoaiPathDraftRecordToken(record) !== token.token) throw new Error('Resolved SoAI link projection token mismatch.');
            const literal = currentSegment.display.slice(cursor, token.startIndex);
            if (literal) segments.push({ display: literal, source: literal, link: false, record: null });
            segments.push({ display: resolveSoaiPathDraftRecordTitle(record), source: token.token, link: true, record });
            recordIndex += 1;
            cursor = token.endIndex;
        }
        const tail = currentSegment.display.slice(cursor);
        if (tail) segments.push({ display: tail, source: tail, link: false, record: null });
    }
    if (recordIndex !== records.length) throw new Error('Resolved SoAI link projection record count mismatch.');
    return segments;
};

const buildRestoredProjection = (displayValue: string, sourceValue: string, records: readonly SoaiPathDraftRecord[]): ProjectionSegment[] => {
    const segments: ProjectionSegment[] = [];
    const usedRecords = new Set<SoaiPathDraftRecord>();
    let sourceCursor = 0;
    let displayCursor = 0;
    for (const token of extractSoaiPathTokenTexts(sourceValue)) {
        const literal = sourceValue.slice(sourceCursor, token.startIndex);
        if (displayValue.slice(displayCursor, displayCursor + literal.length) !== literal) throw new Error('Conversation draft SoAI link projection is inconsistent.');
        if (literal) segments.push({ display: literal, source: literal, link: false, record: null });
        displayCursor += literal.length;
        const matchingRecord = records.find((record) => !usedRecords.has(record) && resolveSoaiPathDraftRecordToken(record) === token.token && displayValue.startsWith(resolveSoaiPathDraftRecordTitle(record), displayCursor));
        if (matchingRecord === undefined) {
            if (!displayValue.startsWith(token.token, displayCursor)) throw new Error('Conversation draft SoAI link projection is inconsistent.');
            segments.push({ display: token.token, source: token.token, link: false, record: null });
            displayCursor += token.token.length;
        } else {
            const title = resolveSoaiPathDraftRecordTitle(matchingRecord);
            segments.push({ display: title, source: token.token, link: true, record: matchingRecord });
            usedRecords.add(matchingRecord);
            displayCursor += title.length;
        }
        sourceCursor = token.endIndex;
    }
    const tail = sourceValue.slice(sourceCursor);
    if (displayValue.slice(displayCursor) !== tail) throw new Error('Conversation draft SoAI link projection is inconsistent.');
    if (tail) segments.push({ display: tail, source: tail, link: false, record: null });
    return segments;
};

class ComposerSoaiLinkResolutionManager {
    readonly #inputSequence = new SequenceToken();
    readonly #composerSubmitSequence = new SequenceToken();
    readonly #payloadSequence = new SequenceToken();
    #segments: ProjectionSegment[] = [];

    nextInputResolveSeq = (): number => this.#inputSequence.next();
    isInputResolveSeqCurrent = (sequence: number): boolean => this.#inputSequence.isActive(sequence);
    nextComposerSubmitResolveSeq = (): number => this.#composerSubmitSequence.next();
    isComposerSubmitResolveSeqCurrent = (sequence: number): boolean => this.#composerSubmitSequence.isActive(sequence);
    nextPayloadResolveSeq = (): number => this.#payloadSequence.next();
    isPayloadResolveSeqCurrent = (sequence: number): boolean => this.#payloadSequence.isActive(sequence);

    resetToLiteral(value: string): void {
        this.#segments = value ? [{ display: value, source: value, link: false, record: null }] : [];
        this.#inputSequence.invalidate();
    }

    noteDisplayedTextChanged(value: string): void {
        const previous = displayedText(this.#segments);
        if (previous === value) return;
        if (previous.length === 0 || this.#segments.every((segment) => !segment.link)) {
            this.resetToLiteral(value);
            return;
        }
        let prefixLength = 0;
        while (prefixLength < previous.length && prefixLength < value.length && previous[prefixLength] === value[prefixLength]) prefixLength += 1;
        let suffixLength = 0;
        while (suffixLength < previous.length - prefixLength && suffixLength < value.length - prefixLength && previous[previous.length - suffixLength - 1] === value[value.length - suffixLength - 1]) suffixLength += 1;
        let offset = 0;
        for (const segment of this.#segments) {
            const end = offset + segment.display.length;
            if (segment.link && offset < prefixLength && prefixLength < end) prefixLength = offset;
            const suffixStart = previous.length - suffixLength;
            if (segment.link && offset < suffixStart && suffixStart < end) suffixLength = previous.length - end;
            offset = end;
        }
        const nextSegments: ProjectionSegment[] = [];
        offset = 0;
        for (const segment of this.#segments) {
            const end = offset + segment.display.length;
            if (end <= prefixLength) nextSegments.push(segment);
            offset = end;
        }
        const literalEnd = value.length - suffixLength;
        const literal = value.slice(prefixLength, literalEnd);
        if (literal) nextSegments.push({ display: literal, source: literal, link: false, record: null });
        offset = 0;
        const previousSuffixStart = previous.length - suffixLength;
        for (const segment of this.#segments) {
            if (offset >= previousSuffixStart) nextSegments.push(segment);
            offset += segment.display.length;
        }
        this.#segments = nextSegments;
        this.#inputSequence.invalidate();
    }

    commitResolvedSource(rawValue: string, records: readonly SoaiPathDraftRecord[]): string {
        const segments = buildResolvedProjection(this.#segments, rawValue, records);
        this.#segments = segments;
        return displayedText(segments);
    }

    validateRestore(displayValue: string, sourceValue: string, records: readonly SoaiPathDraftRecord[]): void {
        buildRestoredProjection(displayValue, sourceValue, records);
    }

    restore(displayValue: string, sourceValue: string, records: readonly SoaiPathDraftRecord[]): void {
        this.#segments = buildRestoredProjection(displayValue, sourceValue, records);
    }

    sourceForDisplayedText(value: string): string {
        return displayedText(this.#segments) === value ? sourceText(this.#segments) : value;
    }

    materializeRecord(record: SoaiPathDraftRecord): void {
        const index = this.#segments.findIndex((segment) => segment.record === record);
        if (index < 0) return;
        const segment = this.#segments[index];
        if (segment === undefined) return;
        this.#segments[index] = { display: segment.display, source: segment.display, link: false, record: null };
    }
}

export { ComposerSoaiLinkResolutionManager };
