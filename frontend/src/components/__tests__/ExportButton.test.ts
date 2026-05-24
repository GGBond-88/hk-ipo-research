import { describe, it, expect } from 'vitest';
import { toCsvContent, sanitizeFilename } from '../ExportButton';

describe('toCsvContent', () => {
  it('returns header-only CSV when rows are empty', () => {
    const result = toCsvContent(['Name', 'Value', 'Date'], []);
    expect(result).toBe('"Name","Value","Date"');
  });

  it('formats single row correctly', () => {
    const result = toCsvContent(['Name', 'Value'], [
      ['Alice', '100'],
    ]);
    expect(result).toBe('"Name","Value"\n"Alice","100"');
  });

  it('formats multiple rows correctly', () => {
    const result = toCsvContent(['Name', 'Value'], [
      ['Alice', '100'],
      ['Bob', '200'],
      ['Charlie', '300'],
    ]);
    const lines = result.split('\n');
    expect(lines).toHaveLength(4); // header + 3 rows
    expect(lines[0]).toBe('"Name","Value"');
    expect(lines[1]).toBe('"Alice","100"');
    expect(lines[2]).toBe('"Bob","200"');
    expect(lines[3]).toBe('"Charlie","300"');
  });

  it('escapes double quotes in cell values', () => {
    const result = toCsvContent(['Description'], [
      ['Company "ABC" Ltd.'],
    ]);
    expect(result).toBe('"Description"\n"Company ""ABC"" Ltd."');
  });

  it('escapes multiple double quotes in a single cell', () => {
    const result = toCsvContent(['Name'], [
      ['The "Best" "Company" Ever'],
    ]);
    expect(result).toBe('"Name"\n"The ""Best"" ""Company"" Ever"');
  });

  it('handles cells containing commas', () => {
    const result = toCsvContent(['Name', 'Address'], [
      ['Alice', 'Room 1, Floor 2, Building A'],
    ]);
    // Comma should be inside the quoted cell, not as a separator
    const lines = result.split('\n');
    expect(lines).toHaveLength(2);
    expect(lines[1]).toBe('"Alice","Room 1, Floor 2, Building A"');
  });

  it('handles cells containing newlines in the value', () => {
    const result = toCsvContent(['Description'], [
      ['Line 1\nLine 2'],
    ]);
    // Note: newlines inside cells are stored literally (not escaped by RFC 4180)
    expect(result).toBe('"Description"\n"Line 1\nLine 2"');
  });

  it('handles empty string cells', () => {
    const result = toCsvContent(['A', 'B', 'C'], [
      ['', '', ''],
    ]);
    expect(result).toBe('"A","B","C"\n"","",""');
  });

  it('handles numeric values as strings', () => {
    const result = toCsvContent(['Year', 'Amount'], [
      ['2023', '1234.56'],
      ['2024', '7890.12'],
    ]);
    const lines = result.split('\n');
    expect(lines).toHaveLength(3);
    expect(lines[1]).toBe('"2023","1234.56"');
    expect(lines[2]).toBe('"2024","7890.12"');
  });

  it('handles zero-length headers array with zero rows', () => {
    const result = toCsvContent([], []);
    expect(result).toBe('');
  });

  it('handles zero-length headers array with rows (degenerate)', () => {
    const result = toCsvContent([], [['a', 'b']]);
    // Header line is empty, data line has joined cells
    expect(result).toBe('\n"a","b"');
  });

  it('handles special characters (backslash, ampersand, percent)', () => {
    const result = toCsvContent(['Code'], [
      ['A&B\\C%D'],
    ]);
    expect(result).toBe('"Code"\n"A&B\\C%D"');
  });

  it('does not double-escape already-escaped quotes', () => {
    // If input contains escaped quotes `""`, they become `""""` in output
    const result = toCsvContent(['Value'], [
      ['pre""post'],
    ]);
    expect(result).toBe('"Value"\n"pre""""post"');
  });
});

describe('sanitizeFilename', () => {
  it('replaces whitespace with underscores', () => {
    expect(sanitizeFilename('My UoP Chart')).toBe('My_UoP_Chart');
  });

  it('replaces multiple whitespace with single underscores', () => {
    expect(sanitizeFilename('Revenue  By   Sector')).toBe('Revenue_By_Sector');
  });

  it('replaces backslash with underscore', () => {
    expect(sanitizeFilename('Path\\Name')).toBe('Path_Name');
  });

  it('replaces forward slash with underscore', () => {
    expect(sanitizeFilename('Q1/Q2 Analysis')).toBe('Q1_Q2_Analysis');
  });

  it('replaces colon with underscore', () => {
    expect(sanitizeFilename('Report: Annual')).toBe('Report__Annual');
  });

  it('replaces asterisk with underscore', () => {
    expect(sanitizeFilename('Note*Important')).toBe('Note_Important');
  });

  it('replaces question mark with underscore', () => {
    expect(sanitizeFilename('Why? What?')).toBe('Why__What_');
  });

  it('replaces double quote with underscore', () => {
    expect(sanitizeFilename('Company "ABC" Ltd.')).toBe('Company__ABC__Ltd.');
  });

  it('replaces less-than with underscore', () => {
    expect(sanitizeFilename('A<B')).toBe('A_B');
  });

  it('replaces greater-than with underscore', () => {
    expect(sanitizeFilename('A>B')).toBe('A_B');
  });

  it('replaces pipe with underscore', () => {
    expect(sanitizeFilename('A|B')).toBe('A_B');
  });

  it('handles label with multiple forbidden characters', () => {
    expect(sanitizeFilename('Q1/Q2: Revenue* Analysis?')).toBe(
      'Q1_Q2__Revenue__Analysis_',
    );
  });

  it('preserves alphanumeric characters as-is', () => {
    expect(sanitizeFilename('Revenue2024')).toBe('Revenue2024');
  });

  it('preserves dots and hyphens', () => {
    expect(sanitizeFilename('v2.0-final')).toBe('v2.0-final');
  });

  it('returns empty string for empty input', () => {
    expect(sanitizeFilename('')).toBe('');
  });

  it('returns underscore-only for label of only whitespace', () => {
    expect(sanitizeFilename('   ')).toBe('_');
  });
});
