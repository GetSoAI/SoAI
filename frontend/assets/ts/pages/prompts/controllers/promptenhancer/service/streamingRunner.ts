/* SoAI - Prompts page streaming runner [frontend/assets/ts/pages/prompts/controllers/promptenhancer/service/streamingRunner.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { runOpenAiModelTestStream } from '@core/openai/modelTestStreamClient.ts';
import { createWebSocketRunId } from '@core/websocketclient/runCorrelation.ts';

type PromptEnhancerStreamingRunnerOptions = {
    modelId: string;
    systemPrompt: string;
    content: string;
    signal: AbortSignal;
    onChunk: (chunk: string) => void;
};

const runPromptEnhancerStreamingRequest = async (options: PromptEnhancerStreamingRunnerOptions): Promise<{ output: string }> => {
    let output = '';
    const runId = createWebSocketRunId('ws_prompt_enhancer');

    await runOpenAiModelTestStream({
        runId,
        request: {
            model: options.modelId,
            stream: true,
            reasoningEffort: 'none',
            messages: [
                { role: 'system', content: options.systemPrompt },
                { role: 'user', content: options.content }
            ]
        },
        signal: options.signal,
        cancelReason: i18n.t('prompts.enhancer.cancelReason'),
        errorMessageFallback: i18n.t('prompts.enhancer.errors.generic'),
        onAssistantTextDelta: (delta) => {
            output += delta;
            options.onChunk(delta);
        }
    });

    return { output };
};

export { runPromptEnhancerStreamingRequest };
