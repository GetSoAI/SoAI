/* SoAI - Shared concurrency sequence token [frontend/assets/ts/core/concurrency/sequenceToken.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

class SequenceToken {
    #token: number = 0;

    get value(): number {
        return this.#token;
    }

    next(): number {
        this.#token += 1;
        return this.#token;
    }

    isActive(token: number): boolean {
        return token === this.#token;
    }

    invalidate(): void {
        this.#token += 1;
    }
}

export { SequenceToken };
