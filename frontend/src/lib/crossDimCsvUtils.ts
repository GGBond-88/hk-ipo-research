import type { CrossDimRow } from './sharedTypes';

/** Fields in CrossDimRow that hold numeric (amount/percentage) values. */
const NUMERIC_KEYS: Set<keyof CrossDimRow> = new Set([
  'percentage',
  'amount_hkd_million',
  'total_net_proceeds',
]);

/**
 * Derive a CSV-safe string value for a CrossDimRow field.
 *
 * Mirrors ScatterChart.getAxisValue() semantics:
 * - Numeric fields (percentage, amount_hkd_million, total_net_proceeds):
 *   null/undefined -> '0'
 * - Categorical fields (enrichment tags):
 *   null/undefined -> 'N/A' (consistent with chart rendering)
 */
export function csvValueForCrossDim(
  key: keyof CrossDimRow,
  val: CrossDimRow[keyof CrossDimRow] | undefined,
): string {
  if (val !== null && val !== undefined) {
    return String(val);
  }
  return NUMERIC_KEYS.has(key) ? '0' : 'N/A';
}
