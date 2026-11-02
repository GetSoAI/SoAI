/* SoAI - Native workspace slot ownership contracts [frontend/assets/ts/core/pagepanes/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RoutePane } from '@core/routing/router/RoutePane.ts';
import { isString } from '@core/typeGuards.ts';

const PAGE_PANE_ID_LIMIT = 64;
const PAGE_PANE_ROUTE_LIMIT = 8192;
const PAGE_PANE_RECORD_LIMIT = 65536;
const isPagePaneIdentity = <Value>(value: Value): value is Value & string => isString(value) && value.length <= PAGE_PANE_ID_LIMIT && /^[A-Za-z0-9_-]+$/u.test(value);

interface PagePaneSlot {
    readonly pane: RoutePane;
    readonly root: HTMLElement;
    readonly outlet: HTMLElement;
    focusOrdinal: number;
    parkedOrdinal: number;
    state: 'mounted' | 'opening' | 'parked' | 'closing';
    admitted: boolean;
}

export type { PagePaneSlot };
export { PAGE_PANE_ID_LIMIT, PAGE_PANE_ROUTE_LIMIT, PAGE_PANE_RECORD_LIMIT, isPagePaneIdentity };
