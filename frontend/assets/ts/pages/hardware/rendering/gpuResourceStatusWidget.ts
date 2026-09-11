/* SoAI - Local GPU resource availability presentation [frontend/assets/ts/pages/hardware/rendering/gpuResourceStatusWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { formatRelativeTime } from '@core/primitives/dateTime.ts';
import { i18n } from '@core/i18n/index.ts';
import { joinUiHtml, uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { GpuResourceFreshness, HardwareGpuResourceHealth, HardwareGpuResourceState } from '@pages/hardware/controllers/realtime/gpuResourceState.ts';

type GpuResourceStatusIconFactory = (iconName: IconName, options?: IconOptions) => TrustedHtml;

const ATTENTION_HEALTH: ReadonlySet<HardwareGpuResourceHealth> = new Set<HardwareGpuResourceHealth>(['degraded', 'stale', 'unavailable']);

const capabilitiesMessage = (freshness: GpuResourceFreshness, nowMs: number): string => {
    if (freshness.health === 'degraded') {
        return i18n.t('hardware.gpuResources.capabilitiesIncomplete');
    }
    if (freshness.updatedAt === null) {
        return i18n.t('hardware.gpuResources.capabilitiesUnavailable');
    }
    const age = formatRelativeTime(freshness.updatedAt, nowMs);
    return freshness.health === 'stale' ? i18n.t('hardware.gpuResources.capabilitiesStale', { age }) : i18n.t('hardware.gpuResources.capabilitiesRetained', { age });
};

const slotsMessage = (freshness: GpuResourceFreshness, nowMs: number): string => {
    if (freshness.updatedAt === null) {
        return i18n.t('hardware.gpuResources.slotsUnavailable');
    }
    const age = formatRelativeTime(freshness.updatedAt, nowMs);
    return freshness.health === 'stale' ? i18n.t('hardware.gpuResources.slotsStale', { age }) : i18n.t('hardware.gpuResources.slotsRetained', { age });
};

const collectMessages = (state: HardwareGpuResourceState, nowMs: number): string[] => {
    const messages: string[] = [];
    if (ATTENTION_HEALTH.has(state.capabilities.health)) {
        messages.push(capabilitiesMessage(state.capabilities, nowMs));
    }
    if (ATTENTION_HEALTH.has(state.slots.health)) {
        messages.push(slotsMessage(state.slots, nowMs));
    }
    return messages;
};

const resolveSeverity = (state: HardwareGpuResourceState): 'error' | 'warning' => {
    return state.capabilities.health === 'unavailable' || state.slots.health === 'unavailable' ? 'error' : 'warning';
};

const resolveIconName = (state: HardwareGpuResourceState, severity: 'error' | 'warning'): IconName => {
    if (severity === 'error') {
        return 'error';
    }
    return state.capabilities.health === 'stale' || state.slots.health === 'stale' ? 'connection-offline' : 'warning';
};

const renderMessages = (messages: readonly string[]): TrustedHtml => {
    return joinUiHtml(messages.map((message) => uiHtml`<p class="hardware-gpu-resource-status__message">${message}</p>`));
};

const renderGpuResourceStatus = (documentRef: Document, state: HardwareGpuResourceState, permitted: boolean, getIconSync: GpuResourceStatusIconFactory): void => {
    const element = dom.resolve('#hardware-gpu-resource-status', documentRef);
    if (!element) return;
    const messages = permitted ? collectMessages(state, Date.now()) : [];
    element.classList.toggle('u-hidden', messages.length === 0);
    if (messages.length === 0) {
        element.removeAttribute('data-severity');
        return;
    }
    const severity = resolveSeverity(state);
    element.setAttribute('data-severity', severity);
    const retry = i18n.t('pageOutlet.retry');
    const statusIcon = getIconSync(resolveIconName(state, severity), { size: 20, strokeWidth: 1.8 });
    const retryIcon = getIconSync('refresh', { size: 14, strokeWidth: 1.7 });
    dom.setHTML(element, uiHtml`<span class="hardware-gpu-resource-status__icon" aria-hidden="true">${statusIcon}</span><div class="hardware-gpu-resource-status__messages">${renderMessages(messages)}</div><button type="button" class="ui-button ui-button--sm ui-variant-accent hardware-gpu-resource-status__action" data-action="hardware.gpu.retry" aria-label="${uiAttr(retry)}" data-tooltip="${uiAttr(retry)}">${retryIcon}<span>${retry}</span></button>`);
};

export { renderGpuResourceStatus };
export type { GpuResourceStatusIconFactory };
