/* SoAI - Voice call speech buffer controller [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallSpeechBufferController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import { ChatStreamRateTracker } from '@features/chat/public.ts';

const FIRST_NATURAL_BOUNDARY_MIN_CHARS = 24;
const NEXT_NATURAL_BOUNDARY_MIN_CHARS = 56;
const FIRST_FORCED_FALLBACK_CHARS = 56;
const NEXT_FORCED_FALLBACK_CHARS = 120;
const FIRST_FORCED_TIMEOUT_MS = 600;
const NEXT_FORCED_TIMEOUT_MS = 1_200;
const FIRST_FORCED_TIMEOUT_MIN_CHARS = 20;
const NEXT_FORCED_TIMEOUT_MIN_CHARS = 48;
const HARD_SPLIT_CHARS = 180;

class VoiceCallSpeechBufferController {
    readonly #rateTracker = new ChatStreamRateTracker();
    #buffer = '';
    #totalVisibleChars = 0;
    #emittedSegmentCount = 0;
    #bufferStartedAtMs: number | null = null;

    reset(): void {
        this.#rateTracker.reset();
        this.#buffer = '';
        this.#totalVisibleChars = 0;
        this.#emittedSegmentCount = 0;
        this.#bufferStartedAtMs = null;
    }

    hasPendingText(): boolean {
        return this.#buffer.trim().length > 0;
    }

    appendDelta(delta: string, nowMs: number): string[] {
        if (!delta) {
            return [];
        }
        const hasPendingText = this.hasPendingText();
        if (!hasPendingText && !delta.trim()) {
            return [];
        }
        if (!hasPendingText) {
            this.#bufferStartedAtMs = nowMs;
        }
        this.#buffer = `${this.#buffer}${delta}`.trimStart();
        this.#totalVisibleChars += delta.length;
        this.#rateTracker.applySample(this.#totalVisibleChars, nowMs);
        if (!this.hasPendingText()) {
            return [];
        }
        return this.#extractReadySegments(false, nowMs);
    }

    flush(nowMs: number): string[] {
        return this.#extractReadySegments(true, nowMs);
    }

    drainReady(nowMs: number): string[] {
        return this.#extractReadySegments(false, nowMs);
    }

    #extractReadySegments(flush: boolean, nowMs: number): string[] {
        const ready: string[] = [];
        while (this.hasPendingText()) {
            const boundary = this.#resolveNaturalBoundary();
            if (boundary !== null) {
                this.#takeSegment(boundary, nowMs, ready);
                continue;
            }
            if (flush) {
                this.#takeSegment(this.#buffer.length, nowMs, ready);
                continue;
            }
            const forcedBoundary = this.#resolveForcedBoundary(nowMs);
            if (forcedBoundary === null) {
                break;
            }
            this.#takeSegment(forcedBoundary, nowMs, ready);
        }
        return ready;
    }

    #takeSegment(boundary: number, nowMs: number, ready: string[]): void {
        const segment = this.#buffer.slice(0, boundary).trim();
        this.#buffer = this.#buffer.slice(boundary).trimStart();
        if (segment) {
            ready.push(segment);
            this.#emittedSegmentCount += 1;
        }
        this.#bufferStartedAtMs = this.hasPendingText() ? nowMs : null;
    }

    #resolveNaturalBoundary(): number | null {
        const minimum = this.#emittedSegmentCount === 0 ? FIRST_NATURAL_BOUNDARY_MIN_CHARS : NEXT_NATURAL_BOUNDARY_MIN_CHARS;
        if (this.#buffer.length < minimum) {
            return null;
        }
        for (let index = minimum; index < this.#buffer.length; index += 1) {
            const char = this.#buffer[index];
            if (char === '\n' || char === '.' || char === '!' || char === '?') {
                return index + 1;
            }
        }
        return null;
    }

    #resolveForcedBoundary(nowMs: number): number | null {
        const threshold = this.#resolveForcedThreshold(nowMs);
        const trimmedLength = this.#buffer.trim().length;
        const timeoutThreshold = this.#emittedSegmentCount === 0 ? FIRST_FORCED_TIMEOUT_MIN_CHARS : NEXT_FORCED_TIMEOUT_MIN_CHARS;
        const timeoutMs = this.#emittedSegmentCount === 0 ? FIRST_FORCED_TIMEOUT_MS : NEXT_FORCED_TIMEOUT_MS;
        const ageMs = this.#bufferStartedAtMs === null ? 0 : nowMs - this.#bufferStartedAtMs;
        if (trimmedLength < threshold && (trimmedLength < timeoutThreshold || ageMs < timeoutMs)) {
            return null;
        }
        const limit = trimmedLength >= threshold ? threshold : trimmedLength;
        return this.#resolveWordBoundary(limit) ?? Math.min(this.#buffer.length, Math.floor(limit));
    }

    #resolveForcedThreshold(nowMs: number): number {
        const rate = this.#rateTracker.resolveRate(nowMs);
        if (rate <= 0) {
            return this.#emittedSegmentCount === 0 ? FIRST_FORCED_FALLBACK_CHARS : NEXT_FORCED_FALLBACK_CHARS;
        }
        if (this.#emittedSegmentCount === 0) {
            return Math.round(clampNumber(rate * 0.8, 24, 72));
        }
        return Math.round(clampNumber(rate * 1.6, 56, HARD_SPLIT_CHARS));
    }

    #resolveWordBoundary(limit: number): number | null {
        const boundedLimit = Math.max(1, Math.min(this.#buffer.length, Math.floor(limit)));
        const startIndex = Math.min(this.#buffer.length - 1, boundedLimit);
        for (let index = startIndex; index > 0; index -= 1) {
            const char = this.#buffer[index];
            if (char === ' ' || char === '\t' || char === '\n') {
                return index + 1;
            }
        }
        if (this.#buffer.length >= HARD_SPLIT_CHARS) {
            return HARD_SPLIT_CHARS;
        }
        return null;
    }
}

export { VoiceCallSpeechBufferController };
