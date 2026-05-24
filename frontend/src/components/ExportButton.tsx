import { type RefObject } from 'react';
import type { EChartsType } from 'echarts';

interface ExportButtonProps {
  chartRef: RefObject<EChartsType | null>;
  chartLabel: string;
  /** Optional CSV data: { headers: string[], rows: string[][] } */
  csvData?: { headers: string[]; rows: string[][] } | null;
}

export function toCsvContent(headers: string[], rows: string[][]): string {
  const escape = (v: string) => `"${v.replace(/"/g, '""')}"`;
  const headerLine = headers.map(escape).join(',');
  const dataLines = rows.map((row) => row.map(escape).join(','));
  return [headerLine, ...dataLines].join('\n');
}

/** Sanitize a chart label into a safe cross-platform filename.
 *  Replaces whitespace and Windows-forbidden characters (\/:*?""<>|) with underscores. */
export function sanitizeFilename(label: string): string {
  return label
    .replace(/\s+/g, '_')
    .replace(/[\\/:*?"<>|]/g, '_');
}

function triggerDownload(url: string, filename: string): void {
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
}

function downloadBlob(content: string, filename: string, mime: string): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  try {
    triggerDownload(url, filename);
  } finally {
    URL.revokeObjectURL(url);
  }
}

export function ExportButton({ chartRef, chartLabel, csvData }: ExportButtonProps) {
  const handlePng = () => {
    const instance = chartRef?.current;
    if (!instance) return;
    const dataUrl = instance.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#fff' });
    triggerDownload(dataUrl, `${sanitizeFilename(chartLabel)}.png`);
  };

  const handleCsv = () => {
    if (!csvData) return;
    const content = toCsvContent(csvData.headers, csvData.rows);
    downloadBlob(content, `${sanitizeFilename(chartLabel)}.csv`, 'text/csv');
  };

  return (
    <div style={{ display: 'flex', gap: 8 }}>
      <button
        type="button"
        onClick={handlePng}
        style={{ padding: '4px 12px', borderRadius: 4, border: '1px solid #ccc',
                 background: '#fff', cursor: 'pointer', fontSize: 12 }}
      >
        Export PNG
      </button>
      {csvData && (
        <button
          type="button"
          onClick={handleCsv}
          style={{ padding: '4px 12px', borderRadius: 4, border: '1px solid #ccc',
                   background: '#fff', cursor: 'pointer', fontSize: 12 }}
        >
          Export CSV
        </button>
      )}
    </div>
  );
}
