/* SoAI - Shared models chart markup [frontend/assets/ts/core/models/requestdistributionglass/chartMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { buildBarsGlassParts } from '@core/models/requestdistributionglass/bars.ts';
import { buildCoinstackGlassParts } from '@core/models/requestdistributionglass/coinstack.ts';
import { vectorOverlayMarkup } from '@core/models/requestdistributionglass/glassMaterial.ts';
import type { RequestDistributionGlassInput, RequestDistributionGlassParts } from '@core/models/requestdistributionglass/glassParts.ts';
import { buildPieGlassParts } from '@core/models/requestdistributionglass/pie.ts';
import { buildSpheresGlassParts } from '@core/models/requestdistributionglass/spheres.ts';
import type { RequestDistributionChartKind } from '@core/models/requestDistributionKind.ts';

interface RenderRequestDistributionChartOptions extends RequestDistributionGlassInput {
    kind: RequestDistributionChartKind;
}

const STAGE_CLASS = 'distribution-chart-3d__stage';
const EMPTY_CLASS = 'distribution-chart-3d__empty';

const formatStageDimension = (value: number): string => (Math.round(value * 100) / 100).toString();

const buildGlassParts = (options: RenderRequestDistributionChartOptions): RequestDistributionGlassParts => {
    const input: RequestDistributionGlassInput = { width: options.width, height: options.height, dataset: options.dataset, colors: options.colors };
    if (options.kind === 'bars3d') {
        return buildBarsGlassParts(input);
    }
    if (options.kind === 'spheres3d') {
        return buildSpheresGlassParts(input);
    }
    if (options.kind === 'coinstack3d') {
        return buildCoinstackGlassParts(input);
    }
    return buildPieGlassParts(input);
};

const renderRequestDistributionChartMarkup = (options: RenderRequestDistributionChartOptions): TrustedHtml => {
    const parts = buildGlassParts(options);
    const overlay = vectorOverlayMarkup(options.width, options.height, parts.defs, parts.rims);
    const width = formatStageDimension(options.width);
    const height = formatStageDimension(options.height);
    return uiHtml`<div class="${STAGE_CLASS}" style="inset:auto;left:50%;top:50%;width:${width}px;height:${height}px;transform:translate(-50%, -50%)">${parts.bodies}${overlay}</div>`;
};

const renderRequestDistributionEmptyStateMarkup = (text: string): TrustedHtml => uiHtml`<div class="${EMPTY_CLASS}">${text}</div>`;

export { renderRequestDistributionChartMarkup, renderRequestDistributionEmptyStateMarkup };
export type { RenderRequestDistributionChartOptions };
