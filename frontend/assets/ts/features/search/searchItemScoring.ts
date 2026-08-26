/* SoAI - Search feature item scoring [frontend/assets/ts/features/search/searchItemScoring.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getCurrentLocale } from '@core/languageservice/service.ts';
import { matchSearchConfigPath, normalizeSearchMatchQuery } from '@core/search/searchQuery.ts';
import type { SearchItem } from '@core/search/searchTypes.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';

const scoreConfigPathMatch = (configPath: string, normalizedTerm: string): number => {
    const match = matchSearchConfigPath(configPath, normalizedTerm);
    if (match === 'exact') {
        return 120;
    }
    if (match === 'suffix') {
        return 70;
    }
    if (match === 'partial') {
        return 20;
    }
    return 0;
};

const calculateRelevanceScore = (item: SearchItem, normalizedTerm: string): number => {
    if (!normalizedTerm) {
        return 0;
    }
    let score = 0;
    const normalizedName = normalizeSearchMatchQuery(item.name ?? '');
    const normalizedDescription = normalizeSearchMatchQuery(item.description ?? '');
    const normalizedAlias = normalizeSearchMatchQuery(item.alias ?? '');
    const normalizedPlugin = normalizeSearchMatchQuery(item.plugin ?? '');
    if (normalizedName === normalizedTerm) score += 100;
    else if (normalizedName.startsWith(normalizedTerm)) score += 50;
    else if (normalizedName.includes(normalizedTerm)) score += 25;
    if (normalizedDescription && normalizedDescription.includes(normalizedTerm)) score += 10;
    if (normalizedAlias && normalizedAlias.includes(normalizedTerm)) score += 30;
    if (normalizedPlugin && normalizedPlugin.includes(normalizedTerm)) score += 15;
    const configPath = item.configPath ?? '';
    if (configPath) score += scoreConfigPathMatch(configPath, normalizedTerm);
    return score;
};

const deduplicateResults = (results: SearchItem[]): SearchItem[] => {
    const seen = new Set<string>();
    return results.filter((item) => {
        const key = `${item.type}:${item.id}`;
        if (seen.has(key)) {
            return false;
        }
        seen.add(key);
        return true;
    });
};

const sortResultsByRelevance = (results: SearchItem[]): SearchItem[] =>
    results.sort((firstValue, secondValue) => {
        if (isFiniteNumber(firstValue.score) && isFiniteNumber(secondValue.score)) {
            return secondValue.score - firstValue.score;
        }
        if (isFiniteNumber(firstValue.score)) {
            return -1;
        }
        if (isFiniteNumber(secondValue.score)) {
            return 1;
        }
        return (firstValue.name ?? '').localeCompare(secondValue.name ?? '', getCurrentLocale());
    });

export { calculateRelevanceScore, deduplicateResults, sortResultsByRelevance };
