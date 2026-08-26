/* SoAI - Shared UI icon service contracts [frontend/assets/ts/core/ui/icons/iconservice/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type AttrValue = string | number | boolean;

interface IconAttributes {
    [name: string]: AttrValue;
}

interface IconOptions {
    size?: number | undefined;
    width?: number | undefined;
    height?: number | undefined;
    strokeWidth?: number | undefined;
    fill?: string | undefined;
    stroke?: string | undefined;
    className?: string | undefined;
    attributes?: IconAttributes | undefined;
}

interface NormalizedIconOptions {
    size: number | null;
    width: number | null;
    height: number | null;
    strokeWidth: number | null;
    fill: string | null;
    stroke: string | null;
    className: string | null;
}

interface IconDefaultOptions {
    size: number;
    strokeWidth: number;
}

export type { AttrValue, IconAttributes, IconDefaultOptions, IconOptions, NormalizedIconOptions };
