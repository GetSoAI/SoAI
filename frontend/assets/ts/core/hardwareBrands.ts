/* SoAI - Shared frontend hardware brands [frontend/assets/ts/core/hardwareBrands.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type HardwareBrand = 'nvidia' | 'amd' | 'intel' | 'qualcomm' | 'via' | 'unknown';

const BRAND_NVIDIA: HardwareBrand = 'nvidia';
const BRAND_AMD: HardwareBrand = 'amd';
const BRAND_INTEL: HardwareBrand = 'intel';
const BRAND_QUALCOMM: HardwareBrand = 'qualcomm';
const BRAND_VIA: HardwareBrand = 'via';
const BRAND_UNKNOWN: HardwareBrand = 'unknown';

const HARDWARE_BRANDS: readonly HardwareBrand[] = Object.freeze([BRAND_NVIDIA, BRAND_AMD, BRAND_INTEL, BRAND_QUALCOMM, BRAND_VIA, BRAND_UNKNOWN]);

const BRAND_PATTERNS: Record<string, readonly string[]> = Object.freeze({
    [BRAND_NVIDIA]: Object.freeze(['nvidia', 'geforce', 'rtx', 'gtx', 'quadro', 'tesla', 'titan', 'nvs', 'grid']),
    [BRAND_AMD]: Object.freeze(['amd', 'radeon', 'ryzen', 'threadripper', 'epyc', 'athlon', 'sempron', 'phenom', 'turion', 'opteron', 'firepro', 'instinct', 'vega', 'rdna']),
    [BRAND_INTEL]: Object.freeze(['intel', 'core', 'xeon', 'pentium', 'celeron', 'atom', 'arc', 'iris', 'uhd']),
    [BRAND_QUALCOMM]: Object.freeze(['qualcomm', 'snapdragon', 'adreno']),
    [BRAND_VIA]: Object.freeze(['via', 'centaur', 'zhaoxin'])
});

const detectHardwareBrand = (name: string | undefined): HardwareBrand => {
    if (name === undefined) return BRAND_UNKNOWN;
    const lower = name.toLowerCase();
    for (const brand of HARDWARE_BRANDS) {
        const patterns = BRAND_PATTERNS[brand];
        if (!patterns) {
            continue;
        }
        if (patterns.some((pattern) => lower.includes(pattern))) {
            return brand;
        }
    }
    return BRAND_UNKNOWN;
};

export { BRAND_NVIDIA, BRAND_AMD, BRAND_INTEL, BRAND_QUALCOMM, BRAND_VIA, BRAND_UNKNOWN, HARDWARE_BRANDS, BRAND_PATTERNS, detectHardwareBrand };

export type { HardwareBrand };
