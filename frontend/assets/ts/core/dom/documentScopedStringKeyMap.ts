/* SoAI - Shared DOM document scoped string key map [frontend/assets/ts/core/dom/documentScopedStringKeyMap.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type DocumentScopedStringKeyMap<TValue> = {
    getMap(document: Document): Map<string, TValue> | null;
    requireMap(document: Document): Map<string, TValue>;
    get(document: Document, key: string): TValue | null;
    set(document: Document, key: string, value: TValue): void;
    delete(document: Document, key: string): void;
    clear(document: Document): void;
};

const createDocumentScopedStringKeyMap = <TValue>(): DocumentScopedStringKeyMap<TValue> => {
    const byDocument = new WeakMap<Document, Map<string, TValue>>();

    const getMap = (document: Document): Map<string, TValue> | null => byDocument.get(document) ?? null;

    const requireMap = (document: Document): Map<string, TValue> => {
        const existing = getMap(document);
        if (existing) {
            return existing;
        }
        const created = new Map<string, TValue>();
        byDocument.set(document, created);
        return created;
    };

    const get = (document: Document, key: string): TValue | null => getMap(document)?.get(key) ?? null;

    const set = (document: Document, key: string, value: TValue): void => {
        requireMap(document).set(key, value);
    };

    const del = (document: Document, key: string): void => {
        getMap(document)?.delete(key);
    };

    const clear = (document: Document): void => {
        const map = getMap(document);
        if (!map) {
            return;
        }
        map.clear();
        byDocument.delete(document);
    };

    return {
        getMap,
        requireMap,
        get,
        set,
        delete: del,
        clear
    };
};

export { createDocumentScopedStringKeyMap };
export type { DocumentScopedStringKeyMap };
