/* SoAI - Shared realtime IDs [frontend/assets/ts/core/realtime/streammanager/resources/ids.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getStreamId } from '@core/constants.ts';

const MODELS = getStreamId('MODELS_COLLECTION');
const PLUGINS = getStreamId('PLUGINS_COLLECTION');
const MODELS_LAST_USED = getStreamId('MODELS_LAST_USED');
const PLUGINS_LAST_USED = getStreamId('PLUGINS_LAST_USED');
const PROMPTS = getStreamId('PROMPTS_COLLECTION');
const PROVIDERS = getStreamId('PROVIDERS_COLLECTION');
const HARDWARE = getStreamId('HARDWARE_SNAPSHOT');
const HARDWARE_GPU_CAPABILITIES = 'hardware.gpu.capabilities';
const HARDWARE_GPU_SLOTS = 'hardware.gpu.slots';
const HARDWARE_GPU_SOAIBENCH_RUNS = 'hardware.gpu.soaibench.runs';
const HARDWARE_PROCESSES = 'hardware.processes';
const STATUS = getStreamId('SYSTEM_STATUS');
const POWER_OPERATIONS = getStreamId('POWER_OPERATIONS');
const METRICS = getStreamId('SYSTEM_METRICS');
const LOGS_CORE = getStreamId('SYSTEM_LOGS_CORE');
const CAPS = getStreamId('PLUGIN_CAPABILITIES_MANIFEST');
const ROUTING = getStreamId('ROUTING_CONFIG');
const VIRTUAL = getStreamId('VIRTUAL_MODELS');
const WEBUI_NOTIFICATIONS = getStreamId('WEBUI_NOTIFICATIONS');
const WEBUI_CHAT_ATTENTION = 'webui.chat.attention';
const WEBUI_CHAT_ACTIVITY = 'webui.chat.activity';
const WEBUI_CHAT_PRESENTATION = 'webui.chat.presentation';

const HARDWARE_CAPABILITIES_RESOURCES: readonly string[] = Object.freeze([HARDWARE_GPU_CAPABILITIES, HARDWARE_GPU_SLOTS, HARDWARE_GPU_SOAIBENCH_RUNS, HARDWARE_PROCESSES, HARDWARE]);
const AUTO_START: ReadonlySet<string> = new Set([MODELS, PLUGINS, CAPS]);
const DETACHED_AUTO_START: ReadonlySet<string> = new Set([MODELS]);
const PRIORITIZED: readonly string[] = Object.freeze([PROMPTS]);

const GB = 1073741824;

export { MODELS, PLUGINS, MODELS_LAST_USED, PLUGINS_LAST_USED, PROMPTS, PROVIDERS, HARDWARE, HARDWARE_GPU_CAPABILITIES, HARDWARE_GPU_SLOTS, HARDWARE_GPU_SOAIBENCH_RUNS, HARDWARE_PROCESSES, HARDWARE_CAPABILITIES_RESOURCES, STATUS, POWER_OPERATIONS, METRICS, LOGS_CORE, CAPS, ROUTING, VIRTUAL, WEBUI_CHAT_ACTIVITY, WEBUI_CHAT_ATTENTION, WEBUI_CHAT_PRESENTATION, WEBUI_NOTIFICATIONS, AUTO_START, DETACHED_AUTO_START, PRIORITIZED, GB };
