/* SoAI - Chat tool live result hydration policy [frontend/assets/ts/features/chat/toolactivity/toolLiveResultPolicy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeToolLeafName } from '@features/chat/toolactivity/toolLeafName.ts';

const DETAIL_HYDRATED_RUNNING_RESULT_TOOL_LEAF_NAMES = new Set(['shell', 'shell_write_stdin', 'subagent_spawn', 'read_video', 'hardware_benchmark']);

const toolRunningResultIsDetailHydrated = (toolName: string): boolean => {
    return DETAIL_HYDRATED_RUNNING_RESULT_TOOL_LEAF_NAMES.has(normalizeToolLeafName(toolName));
};

export { toolRunningResultIsDetailHydrated };
