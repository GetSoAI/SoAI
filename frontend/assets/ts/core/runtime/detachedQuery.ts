/* SoAI - Shared runtime detached query [frontend/assets/ts/core/runtime/detachedQuery.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface DetachedQueryResult {
    pageId: string | null;
}

const parseDetachedQuery = (search: string): DetachedQueryResult => {
    const query = new URLSearchParams(search);
    const pageIdValue = query.get('page');
    return { pageId: pageIdValue ? pageIdValue.trim() || null : null };
};

export { parseDetachedQuery };
export type { DetachedQueryResult };
