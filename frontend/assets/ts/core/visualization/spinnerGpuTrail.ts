/* SoAI - GPU rendering for the authored loading trail [frontend/assets/ts/core/visualization/spinnerGpuTrail.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SpinnerTrailAppearance } from '@core/visualization/protocol.ts';

const VERTEX_SOURCE = `
attribute vec2 position;
void main() {
    gl_Position = vec4(position, 0., 1.);
}`;
const FRAGMENT_SOURCE = `
precision highp float;
uniform vec2 resolution;
uniform float rotation;
uniform vec2 trailSize;
uniform sampler2D gradient;
void main() {
    vec2 offset = gl_FragCoord.xy - resolution * .5;
    float cosine = cos(rotation);
    float sine = sin(rotation);
    vec2 samplePosition = vec2(offset.x * cosine - offset.y * sine, offset.x * sine + offset.y * cosine) / trailSize + .5;
    gl_FragColor = texture2D(gradient, samplePosition);
}`;

const compileTrailShader = (context: WebGLRenderingContext, type: number, source: string): WebGLShader => {
    const shader = context.createShader(type);
    if (!shader) throw new Error('Loading shader allocation failed');
    context.shaderSource(shader, source);
    context.compileShader(shader);
    if (!context.getShaderParameter(shader, context.COMPILE_STATUS)) {
        context.deleteShader(shader);
        throw new Error('Loading shader compilation failed');
    }
    return shader;
};

class SpinnerGpuTrail {
    readonly #canvas: OffscreenCanvas;
    readonly #context: WebGLRenderingContext;
    readonly #program: WebGLProgram;
    readonly #vertices: WebGLBuffer;
    readonly #texture: WebGLTexture;
    readonly #palette: OffscreenCanvasRenderingContext2D;
    readonly #rotation: WebGLUniformLocation;
    readonly #resolution: WebGLUniformLocation;
    readonly #trailSize: WebGLUniformLocation;
    #duration = 1;

    constructor(canvas: OffscreenCanvas) {
        const context = canvas.getContext('webgl', { alpha: true, premultipliedAlpha: true, depth: false, stencil: false, antialias: false });
        const palette = new OffscreenCanvas(1, 1).getContext('2d');
        if (!context || !palette) {
            context?.getExtension('WEBGL_lose_context')?.loseContext();
            throw new Error('GPU loading animation is unavailable');
        }
        const program = context.createProgram();
        const vertices = context.createBuffer();
        const texture = context.createTexture();
        let vertex: WebGLShader | null = null;
        let fragment: WebGLShader | null = null;
        try {
            if (!program || !vertices || !texture) throw new Error('Loading GPU resource allocation failed');
            vertex = compileTrailShader(context, context.VERTEX_SHADER, VERTEX_SOURCE);
            fragment = compileTrailShader(context, context.FRAGMENT_SHADER, FRAGMENT_SOURCE);
            context.attachShader(program, vertex);
            context.attachShader(program, fragment);
            context.linkProgram(program);
            if (!context.getProgramParameter(program, context.LINK_STATUS)) throw new Error('Loading GPU program linking failed');
            context.useProgram(program);
            context.bindBuffer(context.ARRAY_BUFFER, vertices);
            context.bufferData(context.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), context.STATIC_DRAW);
            const position = context.getAttribLocation(program, 'position');
            if (position < 0) throw new Error('Loading GPU position attribute is unavailable');
            context.enableVertexAttribArray(position);
            context.vertexAttribPointer(position, 2, context.FLOAT, false, 0, 0);
            context.bindTexture(context.TEXTURE_2D, texture);
            context.texParameteri(context.TEXTURE_2D, context.TEXTURE_MIN_FILTER, context.LINEAR);
            context.texParameteri(context.TEXTURE_2D, context.TEXTURE_MAG_FILTER, context.LINEAR);
            context.texParameteri(context.TEXTURE_2D, context.TEXTURE_WRAP_S, context.CLAMP_TO_EDGE);
            context.texParameteri(context.TEXTURE_2D, context.TEXTURE_WRAP_T, context.CLAMP_TO_EDGE);
            context.pixelStorei(context.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
            context.pixelStorei(context.UNPACK_FLIP_Y_WEBGL, true);
            const rotation = context.getUniformLocation(program, 'rotation');
            const resolution = context.getUniformLocation(program, 'resolution');
            const gradient = context.getUniformLocation(program, 'gradient');
            const trailSize = context.getUniformLocation(program, 'trailSize');
            if (!rotation || !resolution || !gradient || !trailSize) throw new Error('Loading GPU uniforms are unavailable');
            context.uniform1i(gradient, 0);
            this.#trailSize = trailSize;
            this.#rotation = rotation;
            this.#resolution = resolution;
            this.#program = program;
            this.#vertices = vertices;
            this.#texture = texture;
        } catch (error) {
            context.deleteProgram(program);
            context.deleteBuffer(vertices);
            context.deleteTexture(texture);
            context.getExtension('WEBGL_lose_context')?.loseContext();
            throw error;
        } finally {
            context.deleteShader(vertex);
            context.deleteShader(fragment);
        }
        this.#canvas = canvas;
        this.#context = context;
        this.#palette = palette;
    }

    configure(appearance: SpinnerTrailAppearance): void {
        const context = this.#context;
        if (this.#canvas.width !== appearance.width) this.#canvas.width = appearance.width;
        if (this.#canvas.height !== appearance.height) this.#canvas.height = appearance.height;
        this.#duration = appearance.duration;
        const paletteCanvas = this.#palette.canvas;
        if (paletteCanvas.width !== appearance.trailWidth) paletteCanvas.width = appearance.trailWidth;
        if (paletteCanvas.height !== appearance.trailHeight) paletteCanvas.height = appearance.trailHeight;
        const gradient = this.#palette.createConicGradient(-Math.PI / 2, appearance.trailWidth / 2, appearance.trailHeight / 2);
        for (const stop of appearance.stops) gradient.addColorStop(stop.position, stop.color);
        this.#palette.clearRect(0, 0, appearance.trailWidth, appearance.trailHeight);
        this.#palette.fillStyle = gradient;
        this.#palette.fillRect(0, 0, appearance.trailWidth, appearance.trailHeight);
        context.texImage2D(context.TEXTURE_2D, 0, context.RGBA, context.RGBA, context.UNSIGNED_BYTE, this.#palette.canvas);
        context.viewport(0, 0, appearance.width, appearance.height);
        context.uniform2f(this.#resolution, appearance.width, appearance.height);
        context.uniform2f(this.#trailSize, appearance.trailWidth, appearance.trailHeight);
    }

    draw(elapsed: number): void {
        const context = this.#context;
        if (context.isContextLost()) throw new Error('Loading GPU context was lost');
        context.uniform1f(this.#rotation, ((elapsed % this.#duration) / this.#duration) * Math.PI * 2);
        context.drawArrays(context.TRIANGLES, 0, 3);
        context.flush();
    }

    dispose(): void {
        this.#context.deleteProgram(this.#program);
        this.#context.deleteBuffer(this.#vertices);
        this.#context.deleteTexture(this.#texture);
        this.#context.getExtension('WEBGL_lose_context')?.loseContext();
    }
}

export { SpinnerGpuTrail };
