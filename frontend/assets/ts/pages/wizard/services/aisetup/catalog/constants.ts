/* SoAI - Wizard AI setup model catalog [frontend/assets/ts/pages/wizard/services/aisetup/catalog/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type ModelCatalogUseCase = 'advanced' | 'balanced' | 'reasoning' | 'light';

interface ModelCatalogEntry {
    id: string;
    name: string;
    family: string;
    qualityOrder: number;
    useCase: ModelCatalogUseCase;
    pluginName: string;
    repository: string;
    file: string;
    quantization: string;
    downloadBytes: number;
    memoryNeededBytes: number;
    architecture: 'dense' | 'moe';
    parametersTotalB: number;
    parametersActiveB: number;
}

const MODEL_CATALOG: readonly ModelCatalogEntry[] = Object.freeze([
    { id: 'gpt-oss-120b-vision', name: 'gpt-oss 120B Vision', family: 'gpt-oss', qualityOrder: 1, useCase: 'reasoning', pluginName: 'llamacpp', repository: 'SoAIHQ/gpt-oss-120b-VISION-v2-GGUF', file: 'gpt-oss-120b-VISION-v2-MXFP4-00001-of-00002.gguf', quantization: 'MXFP4', downloadBytes: 66020146112, memoryNeededBytes: 68167629760, architecture: 'moe', parametersTotalB: 117, parametersActiveB: 5.1 },
    { id: 'qwen3.8-27b', name: 'Qwen3.8 27B', family: 'Qwen', qualityOrder: 2, useCase: 'advanced', pluginName: 'llamacpp', repository: 'SoAIHQ/Qwen3.8-27B-GGUF', file: 'Qwen3.8-27B-Q4_K_M.gguf', quantization: 'Q4_K_M', downloadBytes: 17738321856, memoryNeededBytes: 21496418240, architecture: 'dense', parametersTotalB: 27, parametersActiveB: 27 },
    { id: 'gemma-4-31b', name: 'Gemma 4 31B', family: 'Gemma', qualityOrder: 3, useCase: 'advanced', pluginName: 'llamacpp', repository: 'SoAIHQ/gemma-4-31B-it-GGUF', file: 'gemma-4-31B-it-Q4_K_M.gguf', quantization: 'Q4_K_M', downloadBytes: 19886021696, memoryNeededBytes: 23644118080, architecture: 'dense', parametersTotalB: 31, parametersActiveB: 31 },
    { id: 'qwen3.6-35b-a3b', name: 'Qwen3.6 35B-A3B', family: 'Qwen', qualityOrder: 4, useCase: 'advanced', pluginName: 'llamacpp', repository: 'unsloth/Qwen3.6-35B-A3B-GGUF', file: 'Qwen3.6-35B-A3B-UD-Q4_K_M.gguf', quantization: 'UD-Q4_K_M', downloadBytes: 22134528992, memoryNeededBytes: 24282012640, architecture: 'moe', parametersTotalB: 35, parametersActiveB: 3 },
    { id: 'gemma-4-26b-a4b', name: 'Gemma 4 26B-A4B', family: 'Gemma', qualityOrder: 5, useCase: 'balanced', pluginName: 'llamacpp', repository: 'SoAIHQ/gemma-4-26B-A4B-it-GGUF', file: 'gemma-4-26B-A4B-it-Q4_K_M.gguf', quantization: 'Q4_K_M', downloadBytes: 17989076832, memoryNeededBytes: 20136560480, architecture: 'moe', parametersTotalB: 26, parametersActiveB: 4 },
    { id: 'nemotron-3-nano-30b-a3b', name: 'Nemotron 3 Nano 30B-A3B', family: 'Nemotron', qualityOrder: 6, useCase: 'reasoning', pluginName: 'llamacpp', repository: 'unsloth/Nemotron-3-Nano-30B-A3B-GGUF', file: 'Nemotron-3-Nano-30B-A3B-UD-Q4_K_XL.gguf', quantization: 'UD-Q4_K_XL', downloadBytes: 22833947424, memoryNeededBytes: 24981431072, architecture: 'moe', parametersTotalB: 30, parametersActiveB: 3 },
    { id: 'gpt-oss-20b', name: 'gpt-oss 20B Vision', family: 'gpt-oss', qualityOrder: 7, useCase: 'reasoning', pluginName: 'llamacpp', repository: 'SoAIHQ/gpt-oss-20b-VISION-v2-GGUF', file: 'gpt-oss-20b-VISION-v2-MXFP4.gguf', quantization: 'MXFP4', downloadBytes: 14443767904, memoryNeededBytes: 16591251552, architecture: 'moe', parametersTotalB: 21, parametersActiveB: 3.6 },
    { id: 'gemma-4-12b', name: 'Gemma 4 12B', family: 'Gemma', qualityOrder: 8, useCase: 'balanced', pluginName: 'llamacpp', repository: 'SoAIHQ/gemma-4-12B-it-GGUF', file: 'gemma-4-12B-it-Q4_K_M.gguf', quantization: 'Q4_K_M', downloadBytes: 7556499392, memoryNeededBytes: 9703983040, architecture: 'dense', parametersTotalB: 12, parametersActiveB: 12 },
    { id: 'qwen3.5-9b', name: 'Qwen3.5 9B', family: 'Qwen', qualityOrder: 9, useCase: 'balanced', pluginName: 'llamacpp', repository: 'SoAIHQ/Qwen3.5-9B-GGUF', file: 'Qwen3.5-9B-Q4_K_M.gguf', quantization: 'Q4_K_M', downloadBytes: 6698256960, memoryNeededBytes: 8845740608, architecture: 'dense', parametersTotalB: 9, parametersActiveB: 9 },
    { id: 'gemma-4-e4b', name: 'Gemma 4 E4B', family: 'Gemma', qualityOrder: 10, useCase: 'light', pluginName: 'llamacpp', repository: 'SoAIHQ/gemma-4-E4B-it-GGUF', file: 'gemma-4-E4B-it-Q4_K_M.gguf', quantization: 'Q4_K_M', downloadBytes: 6325665280, memoryNeededBytes: 7936278016, architecture: 'dense', parametersTotalB: 4, parametersActiveB: 4 },
    { id: 'qwen3.5-4b', name: 'Qwen3.5 4B', family: 'Qwen', qualityOrder: 11, useCase: 'light', pluginName: 'llamacpp', repository: 'SoAIHQ/Qwen3.5-4B-GGUF', file: 'Qwen3.5-4B-Q4_K_M.gguf', quantization: 'Q4_K_M', downloadBytes: 3455870624, memoryNeededBytes: 5066483360, architecture: 'dense', parametersTotalB: 4, parametersActiveB: 4 },
    { id: 'nemotron-3-nano-4b', name: 'Nemotron 3 Nano 4B', family: 'Nemotron', qualityOrder: 12, useCase: 'light', pluginName: 'llamacpp', repository: 'unsloth/NVIDIA-Nemotron-3-Nano-4B-GGUF', file: 'NVIDIA-Nemotron-3-Nano-4B-Q4_K_M.gguf', quantization: 'Q4_K_M', downloadBytes: 2900295712, memoryNeededBytes: 4510908448, architecture: 'dense', parametersTotalB: 4, parametersActiveB: 4 },
    { id: 'gemma-4-e2b', name: 'Gemma 4 E2B', family: 'Gemma', qualityOrder: 13, useCase: 'light', pluginName: 'llamacpp', repository: 'SoAIHQ/gemma-4-E2B-it-GGUF', file: 'gemma-4-E2B-it-Q4_K_M.gguf', quantization: 'Q4_K_M', downloadBytes: 4413534688, memoryNeededBytes: 6024147424, architecture: 'dense', parametersTotalB: 2, parametersActiveB: 2 },
    { id: 'qwen3.5-2b', name: 'Qwen3.5 2B', family: 'Qwen', qualityOrder: 14, useCase: 'light', pluginName: 'llamacpp', repository: 'SoAIHQ/Qwen3.5-2B-GGUF', file: 'Qwen3.5-2B-Q4_K_M.gguf', quantization: 'Q4_K_M', downloadBytes: 1980392192, memoryNeededBytes: 3591004928, architecture: 'dense', parametersTotalB: 2, parametersActiveB: 2 }
]);

const findModelCatalogEntry = (catalogId: string | null): ModelCatalogEntry | null => MODEL_CATALOG.find((entry) => entry.id === catalogId) ?? null;

export { MODEL_CATALOG, findModelCatalogEntry };
export type { ModelCatalogEntry, ModelCatalogUseCase };
