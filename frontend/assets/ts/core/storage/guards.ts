/* SoAI - Storage runtime value guards [frontend/assets/ts/core/storage/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAnimationSpeed } from '@core/animations/speed.ts';
import { isDateFormatPreference, isMeasurementUnitsPreference, isRegionalLocalePreference } from '@core/localization/public.ts';
import { isInterfaceScalePercent } from '@core/layout/interfaceScale.ts';
import type { AnimationType, ChartColorModeType, ClockFormatType, ImageFitType, ThemeType } from '@core/storage/types.ts';
import { hasFunctionProperty, isObject, isThenable } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { readRequiredStringArrayValue } from '@core/types/payloadArrayReaders.ts';

interface KeyValueStorageContract {
    get: (key: string, defaultValue?: JsonValue | null) => JsonValue | null;
    set: (key: string, value: JsonValue | null) => void;
}

interface StorageServiceContract extends KeyValueStorageContract {
    ready: PromiseLike<JsonValue | null>;
}

interface RecentSearchStorageContract {
    getRecentSearches: () => string[];
    addRecentSearch: (query: string) => void;
    clearRecentSearches: () => void;
}

type StorageGuardCandidate = JsonValue | KeyValueStorageContract | RecentSearchStorageContract | StorageServiceContract | null | undefined;

const isKeyValueStorageContract = (value: StorageGuardCandidate): value is KeyValueStorageContract => isObject(value) && hasFunctionProperty(value, 'get') && hasFunctionProperty(value, 'set');

const isStorageServiceContract = (value: StorageGuardCandidate): value is StorageServiceContract => isObject(value) && isKeyValueStorageContract(value) && 'ready' in value && isThenable(value.ready);

const isRecentSearchStorageContract = (value: StorageGuardCandidate): value is RecentSearchStorageContract => isObject(value) && hasFunctionProperty(value, 'getRecentSearches') && hasFunctionProperty(value, 'addRecentSearch') && hasFunctionProperty(value, 'clearRecentSearches');

const requireRecentSearchStorage = (value: StorageGuardCandidate): RecentSearchStorageContract => {
    if (!isRecentSearchStorageContract(value)) {
        throw new Error('Recent search storage requires getRecentSearches/addRecentSearch/clearRecentSearches');
    }
    return {
        getRecentSearches: (): string[] => readRequiredStringArrayValue(value.getRecentSearches(), 'Recent searches'),
        addRecentSearch: (query: string): void => {
            value.addRecentSearch(query);
        },
        clearRecentSearches: (): void => {
            value.clearRecentSearches();
        }
    };
};

const isThemeType = (value: JsonValue | null | undefined): value is ThemeType => value === 'dark' || value === 'light' || value === 'auto';

const isClockFormatType = (value: JsonValue | null | undefined): value is ClockFormatType => value === '24h' || value === '12h';

const isImageFitType = (value: JsonValue | null | undefined): value is ImageFitType => value === 'contain' || value === 'cover';

const isChartColorModeType = (value: JsonValue | null | undefined): value is ChartColorModeType => value === 'disabled' || value === 'static' || value === 'auto';

const isAnimationType = (value: JsonValue | null | undefined): value is AnimationType => value === 'fade' || value === 'slide' || value === 'scale' || value === 'zoom' || value === 'lateral';

export { isAnimationSpeed, isAnimationType, isChartColorModeType, isClockFormatType, isDateFormatPreference, isImageFitType, isInterfaceScalePercent, isKeyValueStorageContract, isMeasurementUnitsPreference, isRegionalLocalePreference, isStorageServiceContract, isThemeType, requireRecentSearchStorage };
export type { RecentSearchStorageContract };
