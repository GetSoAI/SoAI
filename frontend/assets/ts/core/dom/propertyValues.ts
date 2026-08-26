/* SoAI - Shared DOM property values [frontend/assets/ts/core/dom/propertyValues.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type DomDatasetMap = Record<string, string | number | boolean | null | undefined>;

type DomPropertyValue = string | number | boolean | null | undefined | void | DomDatasetMap;

type DomPropertyMap = Record<string, DomPropertyValue>;

export type { DomDatasetMap, DomPropertyMap, DomPropertyValue };
