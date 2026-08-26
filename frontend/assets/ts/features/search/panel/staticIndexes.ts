/* SoAI - Frontend search panel static indexing [frontend/assets/ts/features/search/panel/staticIndexes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { SearchItem } from '@core/search/searchTypes.ts';
import type { SearchBackendDependencies, SearchIndexKey } from '@features/search/panel/contracts.ts';
import type { SearchBackendState } from '@features/search/panel/state.ts';

interface StaticSearchIndexRefreshContext {
    dependencies: Pick<SearchBackendDependencies, 'staticContributors'>;
    state: SearchBackendState;
    updateSearchIndex: (type: SearchIndexKey, items: SearchItem[]) => void;
}

const refreshStaticSearchIndexes = async (context: StaticSearchIndexRefreshContext): Promise<void> => {
    for (const contributor of context.dependencies.staticContributors) {
        try {
            const items = await contributor.index({ grantedActions: context.state.grantedActions });
            context.updateSearchIndex(contributor.bucket, items);
        } catch (error) {
            errorHandler.error('SearchPanel', `Static search contributor "${contributor.id}" failed`, ensureError(error));
            context.updateSearchIndex(contributor.bucket, []);
        }
    }
};

export { refreshStaticSearchIndexes };
