/* SoAI - Shared header actions contracts [frontend/assets/ts/core/headeractions/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface ActionDefinition {
    id: string;
    order: number;
    priority: number;
    icon: string | null;
    label: string | null;
    tooltip: string | null;
    ariaLabel: string | null;
    className: string;
    persistent: boolean;
    disabled: boolean;
    badge: string | null;
    analyticsId: string | null;
    pressed: boolean | null;
    onClick?: ((event: Event) => void) | undefined;
}

interface ContextPayload {
    visible: boolean;
    priority: number;
    order: number | null;
    icon: string | null;
    label: string | null;
    tooltip: string | null;
    ariaLabel: string | null;
    className: string | null;
    disabled: boolean;
    badge: string | null;
    analyticsId: string | null;
    pressed: boolean | null;
    onClick: ((event: Event) => void) | null;
    updatedAt: number;
}

interface Renderable {
    id: string;
    visible: boolean;
    icon: string | null;
    label: string | null;
    tooltip: string | null;
    ariaLabel: string | null;
    className: string;
    disabled: boolean;
    badge: string | null;
    analyticsId: string | null;
    pressed: boolean | null;
    order: number;
    priority: number;
    onClick: ((event: Event) => void) | null;
}

interface RegistryEntry {
    id: string;
    definition: ActionDefinition;
    contexts: Map<string, ContextPayload>;
    renderable: Renderable | null;
}

interface ActionSnapshot {
    actions: Renderable[];
}

type SubscriberCallback = (snapshot: ActionSnapshot) => void;

interface DefinitionInput {
    id?: string | undefined;
    order?: number | undefined;
    priority?: number | undefined;
    icon?: string | undefined;
    label?: string | undefined;
    tooltip?: string | undefined;
    ariaLabel?: string | undefined;
    className?: string | undefined;
    persistent?: boolean | undefined;
    disabled?: boolean | undefined;
    badge?: string | undefined;
    analyticsId?: string | undefined;
    pressed?: boolean | undefined;
    onClick?: ((event: Event) => void) | undefined;
}

interface PayloadInput {
    visible?: boolean | undefined;
    priority?: number | undefined;
    order?: number | undefined;
    icon?: string | undefined;
    label?: string | undefined;
    tooltip?: string | undefined;
    ariaLabel?: string | undefined;
    className?: string | undefined;
    disabled?: boolean | undefined;
    badge?: string | undefined;
    analyticsId?: string | undefined;
    pressed?: boolean | undefined;
    onClick?: ((event: Event) => void) | undefined;
}

export type { ActionDefinition, ContextPayload, Renderable, RegistryEntry, ActionSnapshot, SubscriberCallback, DefinitionInput, PayloadInput };
