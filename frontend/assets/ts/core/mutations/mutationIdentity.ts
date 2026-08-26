/* SoAI - Server-anchored UUIDv7 mutation identity clock [frontend/assets/ts/core/mutations/mutationIdentity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError } from '@core/apiError.ts';
import { getGlobalScope } from '@core/environment/public.ts';
import { reanchorServerTime, resolveServerTimeMs, ServerTimeClock } from '@core/time/serverTimeClock.ts';
import { isFunction } from '@core/typeGuards.ts';
import { isJsonObject } from '@core/types/jsonValues.ts';

const MUTATION_REQUEST_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

type RandomByteFiller = (target: Uint8Array) => void;

const isMutationRequestId = (value: string): boolean => MUTATION_REQUEST_ID.test(value);

const requireMutationRequestId = (value: string): string => {
    const normalized = value.trim();
    if (!isMutationRequestId(normalized)) throw new Error('Mutation request identity must be a lowercase UUIDv7');
    return normalized;
};

const defaultRandomByteFiller: RandomByteFiller = (target): void => {
    const cryptoApi = getGlobalScope().crypto;
    if (!cryptoApi || !isFunction(cryptoApi.getRandomValues)) throw new Error('Secure random generation is unavailable');
    cryptoApi.getRandomValues(target);
};

const byteHex = (value: number): string => value.toString(16).padStart(2, '0');

const createMutationRequestIdFromTimestamp = (timestampMs: number, fillRandomBytes: RandomByteFiller): string => {
    const bytes = new Uint8Array(16);
    const randomBytes = new Uint8Array(10);
    fillRandomBytes(randomBytes);
    let remainingTimestamp = timestampMs;
    for (let index = 5; index >= 0; index -= 1) {
        bytes[index] = remainingTimestamp % 256;
        remainingTimestamp = Math.floor(remainingTimestamp / 256);
    }
    for (let index = 0; index < randomBytes.length; index += 1) bytes[index + 6] = randomBytes[index] ?? 0;
    bytes[6] = ((bytes[6] ?? 0) & 0x0f) | 0x70;
    bytes[8] = ((bytes[8] ?? 0) & 0x3f) | 0x80;
    const hex = Array.from(bytes, byteHex).join('');
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
};

class MutationIdentityClock {
    readonly #serverTimeClock: ServerTimeClock;
    readonly #fillRandomBytes: RandomByteFiller;

    constructor(serverTimeClock: ServerTimeClock, fillRandomBytes: RandomByteFiller = defaultRandomByteFiller) {
        this.#serverTimeClock = serverTimeClock;
        this.#fillRandomBytes = fillRandomBytes;
    }

    observeServerTime(serverTimeMs: number): void {
        this.#serverTimeClock.observe(serverTimeMs);
    }

    reanchorServerTime(serverTimeMs: number): void {
        this.#serverTimeClock.reanchor(serverTimeMs);
    }

    create(): string {
        return createMutationRequestIdFromTimestamp(this.#serverTimeClock.now(), this.#fillRandomBytes);
    }
}

const createMutationRequestId = (): string => createMutationRequestIdFromTimestamp(resolveServerTimeMs(), defaultRandomByteFiller);

const recoverMutationIdentityTimeSkew = <T>(error: T): boolean => {
    if (!(error instanceof APIError) || error.code !== 'identity_time_skew' || !isJsonObject(error.payload)) return false;
    const nestedErrorPayload = error.payload['error'];
    const errorPayload = isJsonObject(nestedErrorPayload) ? nestedErrorPayload : error.payload;
    const details = errorPayload['details'];
    if (!isJsonObject(details)) return false;
    const serverTimeMs = details['server_time_ms'];
    if (!Number.isSafeInteger(serverTimeMs) || typeof serverTimeMs !== 'number' || serverTimeMs < 0) return false;
    reanchorServerTime(serverTimeMs);
    return true;
};

export { createMutationRequestId, isMutationRequestId, MutationIdentityClock, recoverMutationIdentityTimeSkew, requireMutationRequestId };
export type { RandomByteFiller };
