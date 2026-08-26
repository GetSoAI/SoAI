/* SoAI - Shared discovery service constants [frontend/assets/ts/core/discoveryservice/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const READY_EVENT = 'soai:core.discovery:ready';

const DEFAULT_API_PORT = 5090;
const DISCOVERY_PORTS: readonly number[] = Object.freeze([7950, 7951, 7952, 7953, 7954, 7955, 7956, 7957, 7958, 7959, 7960]);

const DISCOVERY_TIMEOUT_MS = 2000;

const HEALTH_PROBE_PATH = '/api/v1/system/health';

export { DEFAULT_API_PORT, DISCOVERY_PORTS, DISCOVERY_TIMEOUT_MS, HEALTH_PROBE_PATH, READY_EVENT };
