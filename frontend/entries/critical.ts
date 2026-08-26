/* SoAI - Frontend critical entry [frontend/entries/critical.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { initializeCspNonceSupport } from '../assets/ts/app/critical/cspNonce.ts';
import { initializeDiagnostics } from '../assets/ts/app/critical/diagnostics.ts';
import { startPreloaderLogo } from '../assets/ts/app/critical/preloaderLogo.ts';
import { initializeThemePreference } from '../assets/ts/critical/themeInit.ts';
import { initializeWindowIdentity } from '../assets/ts/app/critical/windowIdentity.ts';
import { startCachedWallpaperReadiness } from '../assets/ts/core/backgroundtasks/wallpaperReadiness.ts';
import './basePath.ts';

initializeCspNonceSupport();
initializeWindowIdentity();
initializeDiagnostics();
initializeThemePreference();
startCachedWallpaperReadiness();
startPreloaderLogo();
