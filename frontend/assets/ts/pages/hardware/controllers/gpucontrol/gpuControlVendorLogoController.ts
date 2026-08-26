/* SoAI - Hardware page GPU control vendor logo controller [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpuControlVendorLogoController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveAssetPath } from '@core/assetPaths.ts';
import { BRAND_AMD, BRAND_INTEL, BRAND_NVIDIA, detectHardwareBrand, type HardwareBrand } from '@core/hardwareBrands.ts';
import type { GpuCapabilities } from '@core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts';
import type { SecurityService } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

type GpuLogoBrand = 'nvidia' | 'amd' | 'intel';

const AMD_VENDOR_ID = 4098;
const INTEL_VENDOR_ID = 32902;
const NVIDIA_VENDOR_ID = 4318;

const GPU_VENDOR_LOGO_PATHS: Readonly<Record<GpuLogoBrand, string>> = Object.freeze({
    nvidia: 'img/logo/nvidia-hardware-logo.png',
    amd: 'img/logo/amd-hardware-logo.png',
    intel: 'img/logo/intel-hardware-logo.png'
});

const GPU_VENDOR_LABELS: Readonly<Record<GpuLogoBrand, string>> = Object.freeze({
    nvidia: 'NVIDIA',
    amd: 'AMD',
    intel: 'Intel'
});

const isGpuLogoBrand = (brand: HardwareBrand): brand is GpuLogoBrand => brand === BRAND_NVIDIA || brand === BRAND_AMD || brand === BRAND_INTEL;

const detectGpuLogoBrandFromVendorId = (vendorId: number | undefined): GpuLogoBrand | null => {
    if (vendorId === NVIDIA_VENDOR_ID) return 'nvidia';
    if (vendorId === AMD_VENDOR_ID) return 'amd';
    if (vendorId === INTEL_VENDOR_ID) return 'intel';
    return null;
};

const detectGpuLogoBrandFromText = (value: string | undefined): GpuLogoBrand | null => {
    const brand = detectHardwareBrand(value);
    return isGpuLogoBrand(brand) ? brand : null;
};

const detectGpuLogoBrand = (caps: GpuCapabilities): GpuLogoBrand | null => {
    return detectGpuLogoBrandFromText(caps.vendor) ?? detectGpuLogoBrandFromText(caps.type) ?? detectGpuLogoBrandFromVendorId(caps.vendorId) ?? detectGpuLogoBrandFromText(caps.name);
};

const renderGpuVendorLogo = (caps: GpuCapabilities, security: SecurityService): string => {
    const brand = detectGpuLogoBrand(caps);
    if (!brand) return '';
    const source = security.escapeAttribute(resolveAssetPath(GPU_VENDOR_LOGO_PATHS[brand]));
    const alt = security.escapeAttribute(`${GPU_VENDOR_LABELS[brand]} GPU`);
    return `<img src="${source}" alt="${alt}" class="gpu-control-vendor-logo" loading="lazy" decoding="async">`;
};

export { renderGpuVendorLogo };
