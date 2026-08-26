/* SoAI - Models feature model search types [frontend/assets/ts/features/models/modals/downloadmodal/modelSearchTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';

interface ModelSearchResult {
    id?: string;
    name?: string;
    summary?: string;
    source?: string;
    type?: string;
    variants?: JsonValue[];
}

type ModelSearchResults = ModelSearchResult[];

interface RepositoryLinkData {
    url: string;
    label: string;
    badges: JsonValue[];
}

export type { ModelSearchResult, ModelSearchResults, RepositoryLinkData };
