/* SoAI - Terminal page icons [frontend/assets/ts/pages/terminal/rendering/icons.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { IconDefinition } from '@core/routing/pages/pagetypes/public.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';

const ICON_OPTIONS: IconOptions = Object.freeze({ size: 24, strokeWidth: 1.5 });
const TERMINAL_ICON_TEXT_INCREASE: IconDefinition = ['add', ICON_OPTIONS];
const TERMINAL_ICON_TEXT_DECREASE: IconDefinition = ['minus', ICON_OPTIONS];
const TERMINAL_ICON_CLEAR: IconDefinition = ['refresh', ICON_OPTIONS];

const ACTION_ICONS: Readonly<Record<string, IconDefinition>> = Object.freeze({
    '#terminal-text-increase': TERMINAL_ICON_TEXT_INCREASE,
    '#terminal-text-decrease': TERMINAL_ICON_TEXT_DECREASE,
    '#terminal-clear': TERMINAL_ICON_CLEAR
});

export { ACTION_ICONS };
