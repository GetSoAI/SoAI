/* SoAI - Pane chrome and switcher action identities [frontend/assets/ts/core/pagepanes/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

const PAGE_PANE_CLOSE = 'page-pane-close';
const PAGE_PANE_SELECT = 'page-pane-select';
const PAGE_PANE_SPLIT = 'page-pane-split';
const PAGE_PANE_RECOVER = 'page-pane-recover';
const { guard: isPagePaneAction } = createActionIdSet(PAGE_PANE_CLOSE, PAGE_PANE_SELECT, PAGE_PANE_SPLIT, PAGE_PANE_RECOVER);

type PagePaneAction = typeof PAGE_PANE_CLOSE | typeof PAGE_PANE_SELECT | typeof PAGE_PANE_SPLIT | typeof PAGE_PANE_RECOVER;
type PagePaneSelection = { readonly type: 'select' | 'close'; readonly paneId: string } | { readonly type: 'split'; readonly route: string } | { readonly type: 'recover' } | null;

export { PAGE_PANE_CLOSE, PAGE_PANE_SELECT, PAGE_PANE_SPLIT, PAGE_PANE_RECOVER, isPagePaneAction };
export type { PagePaneAction, PagePaneSelection };
