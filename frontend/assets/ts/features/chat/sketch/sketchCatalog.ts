/* SoAI - Frontend chat sketch tool and color catalog [frontend/assets/ts/features/chat/sketch/sketchCatalog.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DrawingDrawOperation, DrawingLimits, DrawingPoint, DrawingShapeOperation, DrawingStrokeOperation } from '@core/drawing/drawingRecords.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';

type ChatSketchFreehandToolType = 'pen' | 'brush' | 'highlighter' | 'eraser';
type ChatSketchShapeType = 'line' | 'rectangle' | 'ellipse';
type ChatSketchDrawOperation = DrawingDrawOperation<ChatSketchFreehandToolType, ChatSketchShapeType>;
type ChatSketchStrokeOperation = DrawingStrokeOperation<ChatSketchFreehandToolType>;
type ChatSketchShapeOperation = DrawingShapeOperation<ChatSketchShapeType>;
type ChatSketchPoint = DrawingPoint;
type ChatSketchToolType = ChatSketchFreehandToolType | ChatSketchShapeType;
type ChatSketchColorId = 'black' | 'grey' | 'red' | 'orange' | 'yellow' | 'green' | 'teal' | 'blue' | 'purple' | 'brown';

type ChatSketchToolSection = 'draw' | 'erase' | 'shape';

type ChatSketchTool = Readonly<{
    type: ChatSketchToolType;
    section: ChatSketchToolSection;
    iconName: IconName;
    defaultSize: number;
    opacity: number;
}>;

type ChatSketchColor = Readonly<{
    id: ChatSketchColorId;
    value: string;
}>;

const CHAT_SKETCH_LIMITS: DrawingLimits = Object.freeze({ retainedOperations: 2048, retainedPoints: 262144, gesturePoints: 32768 });

const CHAT_SKETCH_CANVAS_WIDTH = 1600;
const CHAT_SKETCH_CANVAS_HEIGHT = 1200;
const CHAT_SKETCH_CANVAS_MIN_EXTENT = 64;
const CHAT_SKETCH_CANVAS_MAX_EXTENT = 4096;
const CHAT_SKETCH_BACKGROUND_COLOR = '#ffffff';
const CHAT_SKETCH_SIZE_MIN = 1;
const CHAT_SKETCH_SIZE_MAX = 48;
const CHAT_SKETCH_DEFAULT_TOOL: ChatSketchToolType = 'pen';
const CHAT_SKETCH_FILE_NAME = 'sketch.png';
const CHAT_SKETCH_FILE_TYPE = 'image/png';
const CHAT_SKETCH_DEFAULT_COLOR = '#111111';

const CHAT_SKETCH_TOOLS: ReadonlyArray<ChatSketchTool> = Object.freeze([
    { type: 'pen', section: 'draw', iconName: 'pen', defaultSize: 2, opacity: 1 },
    { type: 'brush', section: 'draw', iconName: 'brush', defaultSize: 8, opacity: 1 },
    { type: 'highlighter', section: 'draw', iconName: 'highlighter', defaultSize: 16, opacity: 0.35 },
    { type: 'eraser', section: 'erase', iconName: 'eraser', defaultSize: 20, opacity: 1 },
    { type: 'line', section: 'shape', iconName: 'shape-line', defaultSize: 3, opacity: 1 },
    { type: 'rectangle', section: 'shape', iconName: 'shape-rectangle', defaultSize: 3, opacity: 1 },
    { type: 'ellipse', section: 'shape', iconName: 'shape-ellipse', defaultSize: 3, opacity: 1 }
]);

const CHAT_SKETCH_COLORS: ReadonlyArray<ChatSketchColor> = Object.freeze([
    { id: 'black', value: CHAT_SKETCH_DEFAULT_COLOR },
    { id: 'grey', value: '#7a7a7a' },
    { id: 'red', value: '#e03131' },
    { id: 'orange', value: '#f76707' },
    { id: 'yellow', value: '#fab005' },
    { id: 'green', value: '#2f9e44' },
    { id: 'teal', value: '#0c8599' },
    { id: 'blue', value: '#1c7ed6' },
    { id: 'purple', value: '#7048e8' },
    { id: 'brown', value: '#8d5a2b' }
]);

const findChatSketchTool = (value: string | undefined): ChatSketchTool | null => CHAT_SKETCH_TOOLS.find((tool) => tool.type === value) ?? null;

const requireChatSketchTool = (type: ChatSketchToolType): ChatSketchTool => {
    const tool = findChatSketchTool(type);
    if (tool === null) throw new Error(`Unknown chat sketch tool ${type}`);
    return tool;
};

const isChatSketchShapeType = (type: ChatSketchToolType): type is ChatSketchShapeType => type === 'line' || type === 'rectangle' || type === 'ellipse';

const normalizeChatSketchColor = (value: string | undefined): string | null => {
    const normalized = value?.trim().toLowerCase() ?? '';
    return /^#[0-9a-f]{6}$/.test(normalized) ? normalized : null;
};

export { CHAT_SKETCH_LIMITS, CHAT_SKETCH_BACKGROUND_COLOR, CHAT_SKETCH_CANVAS_HEIGHT, CHAT_SKETCH_CANVAS_MAX_EXTENT, CHAT_SKETCH_CANVAS_MIN_EXTENT, CHAT_SKETCH_CANVAS_WIDTH, CHAT_SKETCH_COLORS, CHAT_SKETCH_DEFAULT_COLOR, CHAT_SKETCH_DEFAULT_TOOL, CHAT_SKETCH_FILE_NAME, CHAT_SKETCH_FILE_TYPE, CHAT_SKETCH_SIZE_MAX, CHAT_SKETCH_SIZE_MIN, CHAT_SKETCH_TOOLS, findChatSketchTool, isChatSketchShapeType, normalizeChatSketchColor, requireChatSketchTool };
export type { ChatSketchDrawOperation, ChatSketchPoint, ChatSketchShapeOperation, ChatSketchStrokeOperation, ChatSketchColor, ChatSketchColorId, ChatSketchFreehandToolType, ChatSketchShapeType, ChatSketchTool, ChatSketchToolType };
