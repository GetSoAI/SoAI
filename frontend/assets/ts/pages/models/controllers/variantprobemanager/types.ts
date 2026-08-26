/* SoAI - Models page variant probe manager contracts [frontend/assets/ts/pages/models/controllers/variantprobemanager/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { DisplayResult, SpeedTestData } from '@core/speedTest.ts';
import type { Sanitizer } from '@pages/models/contracts/modelsPageTypes.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

export interface SpeedTest {
    getDisplay?(value: SpeedTestData | null): DisplayResult | null;
    formatSample?(source: SpeedTestData | null): string;
    getLoadFactor?(source: SpeedTestData | null): number | null;
}

export interface VariantProbeHost extends PageDomOwnerHost {
    sanitizer: Sanitizer;
    formatNumber(value: number, options?: Intl.NumberFormatOptions): string;
    getIconSync(iconName: IconName, options?: IconOptions): TrustedHtml;
    setUIValue(target: string | Element, value: string | null | undefined, options?: { attribute?: string; allowNull?: boolean }): void;
}

export interface VariantProbeDependencies {
    host: VariantProbeHost;
    speedTest?: SpeedTest;
}

export interface VariantProbeRenderContext {
    host: VariantProbeHost;
    sanitizer: Sanitizer;
    speedTest?: SpeedTest;
    selectedIndex: number | null;
    formatDecimal(value: number | null, fractionDigits?: number): string | null;
}
