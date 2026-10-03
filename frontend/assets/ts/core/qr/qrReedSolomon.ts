/* SoAI - QR Reed-Solomon error correction over GF(256) [frontend/assets/ts/core/qr/qrReedSolomon.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireNonNull } from '@core/assertions.ts';

const QR_FIELD_REDUCTION_POLYNOMIAL = 0x11d;
const QR_FIELD_GENERATOR = 0x02;
const QR_MAX_GENERATOR_DEGREE = 30;

const multiplyGf256 = (left: number, right: number): number => {
    let product = 0;
    for (let bitIndex = 7; bitIndex >= 0; bitIndex -= 1) {
        product = (product << 1) ^ ((product >>> 7) * QR_FIELD_REDUCTION_POLYNOMIAL);
        product ^= ((right >>> bitIndex) & 1) * left;
    }
    return product;
};

const reedSolomonGenerator = (degree: number): Uint8Array => {
    if (!Number.isInteger(degree) || degree < 1 || degree > QR_MAX_GENERATOR_DEGREE) {
        throw new RangeError(`QR Reed-Solomon degree ${degree} is outside 1-${QR_MAX_GENERATOR_DEGREE}`);
    }
    const coefficients = new Uint8Array(degree);
    coefficients[degree - 1] = 1;
    let root = 1;
    for (let rootIndex = 0; rootIndex < degree; rootIndex += 1) {
        coefficients.forEach((coefficient, coefficientIndex) => {
            const nextCoefficient = coefficientIndex + 1 < degree ? requireNonNull(coefficients[coefficientIndex + 1], 'QR generator coefficient') : 0;
            coefficients[coefficientIndex] = multiplyGf256(coefficient, root) ^ nextCoefficient;
        });
        root = multiplyGf256(root, QR_FIELD_GENERATOR);
    }
    return coefficients;
};

const reedSolomonRemainder = (data: Uint8Array, generator: Uint8Array): Uint8Array => {
    const remainder = new Uint8Array(generator.length);
    for (const dataByte of data) {
        const factor = dataByte ^ requireNonNull(remainder[0], 'QR remainder leading coefficient');
        remainder.copyWithin(0, 1);
        remainder[remainder.length - 1] = 0;
        generator.forEach((coefficient, coefficientIndex) => {
            remainder[coefficientIndex] = requireNonNull(remainder[coefficientIndex], 'QR remainder coefficient') ^ multiplyGf256(coefficient, factor);
        });
    }
    return remainder;
};

export { multiplyGf256, reedSolomonGenerator, reedSolomonRemainder };
