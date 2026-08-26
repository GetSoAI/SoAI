/* SoAI - Shared frontend layout header action zone manager public contracts [frontend/assets/ts/core/layout/header/actionzonemanager/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ActionSnapshot, Renderable } from '@core/headeractions/public.ts';
import type { IconApplyConfig } from '@core/layout/HeaderInterface.ts';
import type { TelemetryValue } from '@core/telemetry/contracts.ts';

interface ActionZoneIconsService {
    apply: (targets: IconApplyConfig[]) => Promise<void>;
}

interface ActionZoneManagerHost {
    on: (target: EventTarget, event: string, handler: (event: Event) => void) => (() => void) | void;
    getDom: (key: string) => HTMLElement | null;
    updateAttribute: (element: Element, attr: string, value: string) => void;
    updateText: (element: Element, text: string) => void;
    removeClassName: (element: Element, className: string | string[]) => void;
    addClassName: (element: Element, className: string | string[]) => void;
    logger: (level: string, message: string, data?: TelemetryValue) => void;
    icons: ActionZoneIconsService;
}

interface Action {
    id: string;
    visible?: boolean | undefined;
    disabled?: boolean | undefined;
    label?: string | undefined;
    tooltip?: string | undefined;
    ariaLabel?: string | undefined;
    className?: string | undefined;
    badge?: string | undefined;
    icon?: string | undefined;
    pressed?: boolean | null | undefined;
    order?: number | undefined;
    priority?: number | undefined;
    onClick?: ((event: Event) => void) | undefined;
}

interface ActionEntry {
    id: string;
    element: HTMLButtonElement;
    icon: HTMLSpanElement;
    badge: HTMLSpanElement;
    requestedIcon: string | null;
    renderedIcon: string | null;
    iconApplyInFlight: boolean;
    cleanup: (() => void) | null;
    handler: ((event: Event) => void) | null;
}

interface ActionZoneManagerOptions {
    header: ActionZoneManagerHost;
    hiddenClass: string;
}

interface ActionZoneManagerState {
    container: Element | null;
    subscription: (() => void) | null;
    layoutCleanup: (() => void) | null;
    layoutFrameId: number | null;
    actions: Map<string, ActionEntry>;
}

type HeaderActionInputValue = string | number | boolean | ((event: Event) => void) | null | undefined;
type NormalizeActionArray = (value: readonly Renderable[] | null | undefined) => Action[];
type ReadActionSnapshot = () => ActionSnapshot;

export type { Action, ActionEntry, ActionZoneIconsService, ActionZoneManagerHost, ActionZoneManagerOptions, ActionZoneManagerState, HeaderActionInputValue, NormalizeActionArray, ReadActionSnapshot };
