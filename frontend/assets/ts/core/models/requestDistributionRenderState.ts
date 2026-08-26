/* SoAI - Shared models request distribution render state [frontend/assets/ts/core/models/requestDistributionRenderState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RequestDistributionDataset, RequestDistributionEntry } from '@core/models/requestDistribution.ts';
import type { RequestDistributionChartKind } from '@core/models/requestDistributionKind.ts';
import type { RequestDistributionLegendItem } from '@core/models/requestDistributionRendering.ts';

interface RequestDistributionChartRenderInput {
    kind: RequestDistributionChartKind;
    width: number;
    height: number;
    colors: readonly string[];
    dataset: RequestDistributionDataset;
}

const EMPTY_REQUEST_DISTRIBUTION_SIGNATURE = 'empty';

const renderedSignatures = new WeakMap<HTMLElement, string>();

const describeEntry = (entry: RequestDistributionEntry): string => `${entry.key}${String(entry.value)}${String(entry.swatchIndex)}`;

const describeLegendItem = (item: RequestDistributionLegendItem): string => `${item.label}${item.detail}${item.swatchColor}`;

const computeRequestDistributionChartSignature = (input: RequestDistributionChartRenderInput): string => {
    const geometry = `${input.kind}${String(input.width)}${String(input.height)}`;
    const palette = input.colors.join('');
    const entries = input.dataset.entries.map(describeEntry).join('');
    return `${geometry}${palette}${entries}`;
};

const computeRequestDistributionLegendSignature = (items: readonly RequestDistributionLegendItem[]): string => {
    if (items.length === 0) {
        return EMPTY_REQUEST_DISTRIBUTION_SIGNATURE;
    }
    return items.map(describeLegendItem).join('');
};

const claimRequestDistributionRender = (surface: HTMLElement, signature: string, options: { expectsContent?: boolean } = {}): boolean => {
    const expectsContent = options.expectsContent !== false;
    const isIntact = expectsContent ? surface.childElementCount > 0 : true;
    if (isIntact && renderedSignatures.get(surface) === signature) {
        return false;
    }
    renderedSignatures.set(surface, signature);
    return true;
};

const releaseRequestDistributionRender = (surface: HTMLElement): void => {
    renderedSignatures.delete(surface);
};

export { EMPTY_REQUEST_DISTRIBUTION_SIGNATURE, claimRequestDistributionRender, computeRequestDistributionChartSignature, computeRequestDistributionLegendSignature, releaseRequestDistributionRender };
export type { RequestDistributionChartRenderInput };
