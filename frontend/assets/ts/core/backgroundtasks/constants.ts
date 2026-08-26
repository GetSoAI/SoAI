/* SoAI - Shared background tasks constants [frontend/assets/ts/core/backgroundtasks/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { AUTH_ROUTE_LOGIN, AUTH_ROUTE_WIZARD } from '@core/routing/router/authRouteTarget.ts';

const CONTENT_CHECK_DELAY_MS = 50;
const CONTENT_CHECK_INITIAL_DELAY_MS = 100;
const DEFAULT_OVERLAY_VALUE = 0;
const EXCLUDED_ROUTES: ReadonlySet<string> = new Set([AUTH_ROUTE_LOGIN, AUTH_ROUTE_WIZARD, 'about']);
const MAX_CONTENT_ATTEMPTS = 20;
const MAX_OVERLAY_PERCENT = 100;
const MIN_OVERLAY_PERCENT = 0;
const PAGE_CLASS_PREFIX = 'page-';
const SOLID_BACKGROUND_STYLE_ID = 'dynamic-solid-background-style';
const WALLPAPER_BROWSER_CACHE_KEY = 'soai.ui.wallpaper.cache';
const WALLPAPER_STYLE_ID = 'dynamic-wallpaper-style';

export { CONTENT_CHECK_DELAY_MS, CONTENT_CHECK_INITIAL_DELAY_MS, DEFAULT_OVERLAY_VALUE, EXCLUDED_ROUTES, MAX_CONTENT_ATTEMPTS, MAX_OVERLAY_PERCENT, MIN_OVERLAY_PERCENT, PAGE_CLASS_PREFIX, SOLID_BACKGROUND_STYLE_ID, WALLPAPER_BROWSER_CACHE_KEY, WALLPAPER_STYLE_ID };
