/* SoAI - Generation-aware chat preference reconciliation [frontend/assets/ts/core/storage/chatpreferences/chatPreferenceReconciliation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { cloneJsonObject } from '@core/primitives/clone.ts';

type ChatPreferenceGenerations = Map<string, number>;

const cloneValue = (value: JsonValue): JsonValue => {
    if (Array.isArray(value)) return value.map(cloneValue);
    if (isJsonObject(value)) return Object.fromEntries(Object.entries(value).map(([key, entry]) => [key, cloneValue(entry)]));
    return value;
};

const valuesEqual = (first: JsonValue | undefined, second: JsonValue | undefined): boolean => JSON.stringify(first) === JSON.stringify(second);
const pathKey = (path: readonly string[]): string => path.map((part) => `${part.length}:${part}`).join('|');

const setPath = (target: JsonObject, path: readonly string[], value: JsonValue): void => {
    let current = target;
    for (let index = 0; index < path.length - 1; index += 1) {
        const part = path[index];
        if (part === undefined) throw new Error('Chat preference path is incomplete.');
        const existing = current[part];
        if (!isJsonObject(existing)) current[part] = {};
        const child = current[part];
        if (!isJsonObject(child)) throw new Error('Chat preference path could not be created.');
        current = child;
    }
    const leaf = path[path.length - 1];
    if (leaf === undefined) throw new Error('Chat preference leaf path is missing.');
    current[leaf] = cloneValue(value);
};

const readPath = (source: JsonObject, path: readonly string[]): JsonValue | undefined => {
    let current: JsonValue = source;
    for (const part of path) {
        if (!isJsonObject(current)) return undefined;
        const nextValue: JsonValue | undefined = current[part];
        if (nextValue === undefined) return undefined;
        current = nextValue;
    }
    return current;
};

const visitLeaves = (value: JsonObject, visitor: (path: readonly string[], value: JsonValue) => void, prefix: readonly string[] = []): void => {
    for (const [key, entry] of Object.entries(value)) {
        const path = [...prefix, key];
        if (isJsonObject(entry) && Object.keys(entry).length > 0) visitLeaves(entry, visitor, path);
        else visitor(path, entry);
    }
};

const createSparseDifference = (confirmed: JsonObject, desired: JsonObject): JsonObject => {
    const patch: JsonObject = {};
    visitLeaves(desired, (path, value) => {
        if (!valuesEqual(readPath(confirmed, path), value)) setPath(patch, path, value);
    });
    return patch;
};

const captureLocalChatPreferenceEdits = (observed: JsonObject, live: JsonObject, generations: ChatPreferenceGenerations): JsonObject => {
    visitLeaves(live, (path, value) => {
        if (!valuesEqual(readPath(observed, path), value)) {
            const key = pathKey(path);
            generations.set(key, (generations.get(key) ?? 0) + 1);
        }
    });
    return cloneJsonObject(live);
};

const captureChatPreferenceGenerations = (patch: JsonObject, generations: ChatPreferenceGenerations): ChatPreferenceGenerations => {
    const captured: ChatPreferenceGenerations = new Map();
    visitLeaves(patch, (path) => captured.set(pathKey(path), generations.get(pathKey(path)) ?? 0));
    return captured;
};

const reconcileAuthoritativeChatPreferences = (live: JsonObject, authoritative: JsonObject, generations: ChatPreferenceGenerations, captured: ChatPreferenceGenerations): JsonObject => {
    const reconciled = cloneJsonObject(live);
    visitLeaves(authoritative, (path, value) => {
        const key = pathKey(path);
        if ((generations.get(key) ?? 0) === (captured.get(key) ?? 0)) setPath(reconciled, path, value);
    });
    return reconciled;
};

const mergeChatPreferencePatch = (base: JsonObject, patch: JsonObject): JsonObject => {
    const merged = cloneJsonObject(base);
    visitLeaves(patch, (path, value) => setPath(merged, path, value));
    return merged;
};

export { captureChatPreferenceGenerations, captureLocalChatPreferenceEdits, createSparseDifference, mergeChatPreferencePatch, reconcileAuthoritativeChatPreferences };
export type { ChatPreferenceGenerations };
