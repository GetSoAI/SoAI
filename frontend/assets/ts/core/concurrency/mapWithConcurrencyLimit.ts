/* SoAI - Concurrency-limited asynchronous mapping [frontend/assets/ts/core/concurrency/mapWithConcurrencyLimit.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';

const mapWithConcurrencyLimit = async <T, R>(items: readonly T[], limit: number, task: (value: T) => Promise<R>): Promise<R[]> => {
    const normalizedLimit = Number.isFinite(limit) ? limit : 1;
    const concurrency = Math.floor(clampNumber(normalizedLimit, 1, 16));
    const results: R[] = [];
    const indexedItems: Array<{ index: number; value: T }> = [];
    for (const [index, value] of items.entries()) {
        indexedItems.push({ index, value });
    }
    let position = 0;
    const runWorker = async (): Promise<void> => {
        while (true) {
            const currentIndex = position;
            if (currentIndex >= indexedItems.length) {
                return;
            }
            position += 1;
            const current = indexedItems[currentIndex];
            if (!current) {
                return;
            }
            results[current.index] = await task(current.value);
        }
    };
    await Promise.all(Array.from({ length: Math.min(concurrency, indexedItems.length) }, () => runWorker()));
    return results;
};

export { mapWithConcurrencyLimit };
