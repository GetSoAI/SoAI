/* SoAI - Frontend chat sketch canvas painter [frontend/assets/ts/features/chat/sketch/sketchPainter.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_SKETCH_BACKGROUND_COLOR, requireChatSketchTool } from '@features/chat/sketch/sketchCatalog.ts';
import type { ChatSketchDrawOperation, ChatSketchShapeOperation, ChatSketchStrokeOperation } from '@features/chat/sketch/sketchDocument.ts';

const paintChatSketchBackground = (context: CanvasRenderingContext2D): void => {
    context.save();
    context.globalAlpha = 1;
    context.fillStyle = CHAT_SKETCH_BACKGROUND_COLOR;
    context.fillRect(0, 0, context.canvas.width, context.canvas.height);
    context.restore();
};

const traceStroke = (context: CanvasRenderingContext2D, operation: ChatSketchStrokeOperation): void => {
    const [first, ...rest] = operation.points;
    if (first === undefined) return;
    context.beginPath();
    if (rest.length === 0) {
        context.arc(first.x, first.y, operation.width / 2, 0, Math.PI * 2);
        context.fill();
        return;
    }
    context.moveTo(first.x, first.y);
    for (let index = 0; index < rest.length - 1; index += 1) {
        const control = rest[index];
        const next = rest[index + 1];
        if (control === undefined || next === undefined) continue;
        context.quadraticCurveTo(control.x, control.y, (control.x + next.x) / 2, (control.y + next.y) / 2);
    }
    const last = rest[rest.length - 1];
    if (last !== undefined) context.lineTo(last.x, last.y);
    context.stroke();
};

const traceShape = (context: CanvasRenderingContext2D, operation: ChatSketchShapeOperation): void => {
    const { start, end } = operation;
    context.beginPath();
    if (operation.shape === 'line') {
        context.moveTo(start.x, start.y);
        context.lineTo(end.x, end.y);
    } else if (operation.shape === 'rectangle') {
        context.rect(Math.min(start.x, end.x), Math.min(start.y, end.y), Math.abs(end.x - start.x), Math.abs(end.y - start.y));
    } else {
        context.ellipse((start.x + end.x) / 2, (start.y + end.y) / 2, Math.abs(end.x - start.x) / 2, Math.abs(end.y - start.y) / 2, 0, 0, Math.PI * 2);
    }
    context.stroke();
};

const paintChatSketchOperation = (context: CanvasRenderingContext2D, operation: ChatSketchDrawOperation): void => {
    const tool = requireChatSketchTool(operation.type === 'stroke' ? operation.tool : operation.shape);
    const color = tool.type === 'eraser' ? CHAT_SKETCH_BACKGROUND_COLOR : operation.color;
    context.save();
    context.globalAlpha = tool.opacity;
    context.strokeStyle = color;
    context.fillStyle = color;
    context.lineWidth = operation.width;
    context.lineCap = 'round';
    context.lineJoin = 'round';
    if (tool.type === 'brush') {
        context.shadowColor = color;
        context.shadowBlur = operation.width / 3;
    }
    if (operation.type === 'stroke') {
        traceStroke(context, operation);
    } else {
        traceShape(context, operation);
    }
    context.restore();
};

export { paintChatSketchBackground, paintChatSketchOperation };
