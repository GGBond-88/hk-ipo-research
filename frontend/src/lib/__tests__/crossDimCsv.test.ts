import { describe, it, expect } from 'vitest';
import { csvValueForCrossDim } from '../crossDimCsvUtils';
import type { CrossDimRow } from '../sharedTypes';

// ── csvValueForCrossDim ─────────────────────────────────────────────────────
//
// Mirrors ScatterChart.getAxisValue() behavior:
//   - Numeric keys (percentage, amount_hkd_million, total_net_proceeds):
//     null → '0'
//   - Categorical keys (enrichment tags):
//     null → 'N/A' (matching chart rendering)

describe('csvValueForCrossDim', () => {
  // ── Numeric keys ───────────────────────────────────────────────────────

  it('returns stringified number for numeric key', () => {
    const result = csvValueForCrossDim('percentage', 42.5);
    expect(result).toBe('42.5');
  });

  it('returns "0" for null on numeric key', () => {
    const result = csvValueForCrossDim('amount_hkd_million', null);
    expect(result).toBe('0');
  });

  it('returns "0" for undefined on numeric key', () => {
    const result = csvValueForCrossDim('total_net_proceeds', undefined);
    expect(result).toBe('0');
  });

  it('returns stringified number "0" for numeric zero', () => {
    const result = csvValueForCrossDim('percentage', 0);
    expect(result).toBe('0');
  });

  // ── Categorical keys ───────────────────────────────────────────────────

  it('returns string value for categorical key', () => {
    const result = csvValueForCrossDim('parent_category', 'Growth');
    expect(result).toBe('Growth');
  });

  it('returns "N/A" for null on categorical key', () => {
    const result = csvValueForCrossDim('esg_tag', null);
    expect(result).toBe('N/A');
  });

  it('returns "N/A" for undefined on categorical key', () => {
    const result = csvValueForCrossDim('commitment', undefined);
    expect(result).toBe('N/A');
  });

  it('returns empty string for empty string on categorical key', () => {
    const result = csvValueForCrossDim('geo', '');
    expect(result).toBe('');
  });

  // ── Edge cases ─────────────────────────────────────────────────────────

  it('handles string "-5" numeric-like value on categorical key as string', () => {
    // Negative string on a categorical key — still treated as category
    const result = csvValueForCrossDim('timeline', '-5');
    expect(result).toBe('-5');
  });

  it('handles number NaN-like edge value via String coercion', () => {
    const result = csvValueForCrossDim('percentage', NaN);
    expect(result).toBe('NaN');
  });

  // Verify all known numeric vs categorical keys
  const NUMERIC_KEYS: (keyof CrossDimRow)[] = ['percentage', 'amount_hkd_million', 'total_net_proceeds'];
  const CATEGORICAL_KEYS: (keyof CrossDimRow)[] = [
    'parent_category', 'geo', 'specificity', 'timeline', 'capex_opex', 'commitment', 'esg_tag',
  ];

  it('treats all numeric keys as numeric (null → "0")', () => {
    for (const key of NUMERIC_KEYS) {
      expect(csvValueForCrossDim(key, null)).toBe('0');
    }
  });

  it('treats all categorical keys as categorical (null → "N/A")', () => {
    for (const key of CATEGORICAL_KEYS) {
      expect(csvValueForCrossDim(key, null)).toBe('N/A');
    }
  });
});
