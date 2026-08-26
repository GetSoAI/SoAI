/* SoAI - Shared search validation [frontend/assets/ts/core/search/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SearchIndexContributor, SearchStaticIndexContributor } from '@core/search/protocols.ts';
import { hasFunctionProperty, isObject, isString } from '@core/typeGuards.ts';

interface SearchIndexContributorCandidate {
    readonly id?: string | undefined;
    readonly bucket?: string | undefined;
    readonly source?: string | undefined;
    readonly index?: CallableFunction | undefined;
}

interface SearchStaticIndexContributorCandidate {
    readonly id?: string | undefined;
    readonly bucket?: string | undefined;
    readonly index?: CallableFunction | undefined;
}

const isSearchIndexContributor = <T>(value: T): value is T & SearchIndexContributor => {
    if (!isObject(value)) {
        return false;
    }
    const candidate: SearchIndexContributorCandidate = value;
    return isString(candidate.id) && Boolean(candidate.id.trim()) && isString(candidate.bucket) && isString(candidate.source) && Boolean(candidate.source.trim()) && hasFunctionProperty(candidate, 'index');
};

const isSearchIndexContributorList = <T>(value: T): value is T & readonly SearchIndexContributor[] => {
    if (!Array.isArray(value)) {
        return false;
    }
    return value.every((entry) => isSearchIndexContributor(entry));
};

const isSearchStaticIndexContributor = <T>(value: T): value is T & SearchStaticIndexContributor => {
    if (!isObject(value)) {
        return false;
    }
    const candidate: SearchStaticIndexContributorCandidate = value;
    return isString(candidate.id) && Boolean(candidate.id.trim()) && isString(candidate.bucket) && hasFunctionProperty(candidate, 'index');
};

const isSearchStaticIndexContributorList = <T>(value: T): value is T & readonly SearchStaticIndexContributor[] => {
    if (!Array.isArray(value)) {
        return false;
    }
    return value.every((entry) => isSearchStaticIndexContributor(entry));
};

export { isSearchIndexContributor, isSearchIndexContributorList, isSearchStaticIndexContributor, isSearchStaticIndexContributorList };
