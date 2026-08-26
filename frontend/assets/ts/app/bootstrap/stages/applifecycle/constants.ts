/* SoAI - Frontend application lifecycle constants [frontend/assets/ts/app/bootstrap/stages/applifecycle/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SEARCH_PANEL_SERVICE_ID } from '@core/search/protocols.ts';
import { TASK_MANAGER_SERVICE_ID } from '@core/tasks/protocols.ts';
import { LIVE_STATUS_OVERLAY_SERVICE_ID } from '@features/indicators/constants.ts';
import { RESTART_OVERLAY_SERVICE_ID } from '@features/overlays/public.ts';

export const LAYOUT_REGISTRY_SKIP = new Set<string>(['mainStatusMonitor', 'core.layout.header', 'core.layout.sidebar', TASK_MANAGER_SERVICE_ID, SEARCH_PANEL_SERVICE_ID, LIVE_STATUS_OVERLAY_SERVICE_ID, RESTART_OVERLAY_SERVICE_ID]);
