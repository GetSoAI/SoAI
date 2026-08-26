/* SoAI - Settings feature MCP public contracts [frontend/assets/ts/features/settings/mcp/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { McpManagerHost } from '@features/settings/mcp/mcpManagerTypes.ts';

export type McpServersHost = Pick<McpManagerHost, 'services' | 'view' | 'execution' | 'data' | 'editing'>;
