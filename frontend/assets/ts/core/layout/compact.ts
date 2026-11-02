/* SoAI - Shared compact shell layout policy [frontend/assets/ts/core/layout/compact.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GeometryDimensions } from '@core/layout/elementGeometry.ts';

const isCompactLayout = (dimensions: GeometryDimensions): boolean => dimensions.width <= 1024 || dimensions.height <= 768;

export { isCompactLayout };
