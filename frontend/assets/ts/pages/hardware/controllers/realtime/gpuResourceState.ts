/* SoAI - Hardware GPU resource freshness and update ownership [frontend/assets/ts/pages/hardware/controllers/realtime/gpuResourceState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GpuCapabilitiesResource } from '@core/realtime/streammanager/resources/gpuCapabilitiesResource.ts';
import type { GpuSlotsBuilderResult } from '@core/types/streamTypes.ts';

type HardwareGpuResource = 'capabilities' | 'slots';
type HardwareGpuResourceHealth = 'pending' | 'ready' | 'degraded' | 'stale' | 'unavailable';

interface GpuResourceFreshness {
    generation: number;
    health: HardwareGpuResourceHealth;
    updatedAt: number | null;
}

const USABLE_HEALTH: ReadonlySet<HardwareGpuResourceHealth> = new Set<HardwareGpuResourceHealth>(['ready', 'degraded']);

const resolveCapabilitiesHealth = (value: GpuCapabilitiesResource): HardwareGpuResourceHealth => {
    if (!value.success) {
        return 'unavailable';
    }
    return value.error === undefined ? 'ready' : 'degraded';
};

class HardwareGpuResourceState {
    readonly capabilities: GpuResourceFreshness = { generation: 0, health: 'pending', updatedAt: null };
    readonly slots: GpuResourceFreshness = { generation: 0, health: 'pending', updatedAt: null };
    retainedCapabilities: GpuCapabilitiesResource | null = null;
    retainedSlots: GpuSlotsBuilderResult | null = null;

    invalidate(): void {
        this.unavailable('capabilities');
        this.unavailable('slots');
    }

    usable(resource: HardwareGpuResource): boolean {
        return USABLE_HEALTH.has(this[resource].health);
    }

    unavailable(resource: HardwareGpuResource): void {
        this[resource].generation += 1;
        this[resource].health = 'unavailable';
    }

    stale(resource: HardwareGpuResource): void {
        this[resource].generation += 1;
        this[resource].health = 'stale';
    }

    acceptCapabilities(value: GpuCapabilitiesResource): void {
        this.capabilities.generation += 1;
        this.capabilities.health = resolveCapabilitiesHealth(value);
        if (value.success) {
            this.retainedCapabilities = value;
            this.capabilities.updatedAt = Date.now();
        }
    }

    acceptSlots(value: GpuSlotsBuilderResult): void {
        this.slots.generation += 1;
        this.slots.health = value.error === null ? 'ready' : 'unavailable';
        if (value.error === null) {
            this.retainedSlots = value;
            this.slots.updatedAt = Date.now();
        }
    }
}

export { HardwareGpuResourceState };
export type { GpuResourceFreshness, HardwareGpuResource, HardwareGpuResourceHealth };
