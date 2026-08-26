/* SoAI - Immutable accepted MCP configuration operations [frontend/assets/ts/features/chat/conversationsettings/mcpconversationsettingscontroller/preparedConfigApply.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { executeMcpConfigApply, reconcileCommittedMcpConfig, type ExecuteMcpConfigApplyOptions } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/effects.ts';
import { hasMcpConfigChanges } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/actions.ts';
import type { McpConfig, McpFormValues } from '@features/chat/conversationsettings/settingsModels.ts';

type PreparedMcpConfigApplyOptions = Omit<ExecuteMcpConfigApplyOptions, 'conversationId' | 'baselineConfig' | 'currentValues'> & {
    conversationId: string | null;
    baselineConfig: McpConfig | null;
    currentValues: McpFormValues | null;
    projectionConfig: McpConfig | null;
    settleProjection: (config: McpConfig, reconciled: boolean) => void;
};

const cloneValues = (values: McpFormValues): McpFormValues => ({ ...values, defaultTools: [...values.defaultTools], planTools: [...values.planTools], executeTools: [...values.executeTools], serverConfigs: { ...values.serverConfigs } });
const cloneConfig = (config: McpConfig): McpConfig => ({ ...config, ...cloneValues(config), knowledgeState: config.knowledgeState ? { ...config.knowledgeState } : null });

const prepareMcpConfigApply = (options: PreparedMcpConfigApplyOptions): (() => Promise<boolean>) => {
    const conversationId = options.conversationId;
    const baselineConfig = options.baselineConfig ? cloneConfig(options.baselineConfig) : null;
    const currentValues = options.currentValues ? cloneValues(options.currentValues) : null;
    const projectionConfig = options.projectionConfig ? cloneConfig(options.projectionConfig) : null;
    return async (): Promise<boolean> => {
        if (!conversationId || !baselineConfig || !currentValues) return true;
        if (projectionConfig && !hasMcpConfigChanges(currentValues, baselineConfig)) {
            const updateToken = options.nextUpdateToken();
            const isStillActive = (): boolean => options.isUpdateTokenActive(updateToken, conversationId);
            const result = await reconcileCommittedMcpConfig({
                host: options.host,
                conversationId,
                config: projectionConfig,
                isStillActive,
                writeMcpConfig: options.writeMcpConfig,
                readMcpTools: options.readMcpTools,
                renderConfig: (config) => options.renderConfig(config),
                projectDefaults: options.projectDefaults
            });
            if (result.active && isStillActive()) options.settleProjection(projectionConfig, result.reconciled);
            return result.reconciled;
        }
        return await executeMcpConfigApply({ ...options, conversationId, baselineConfig, currentValues });
    };
};

export { prepareMcpConfigApply };
export type { PreparedMcpConfigApplyOptions };
