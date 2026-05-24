import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { type RefObject } from 'react';
import type { EChartsType } from 'echarts';
import { ExportButton } from '../ExportButton';

// Capture the original document.createElement before any spy wraps it.
const _origCreateElement = document.createElement.bind(document);

function makeChartRef(
  overrides: Partial<EChartsType> = {},
): RefObject<EChartsType | null> {
  const instance = {
    getDataURL: vi.fn().mockReturnValue('data:image/png;base64,mock'),
    ...overrides,
  } as unknown as EChartsType;
  return { current: instance };
}

function makeCsvData(headers: string[], rows: string[][]) {
  return { headers, rows };
}

function mockCreateElement(anchor: HTMLAnchorElement): ReturnType<typeof vi.spyOn> {
  const spy = vi.spyOn(document, 'createElement');
  spy.mockImplementation(
    (tagName: string, options?: ElementCreationOptions) => {
      if (tagName === 'a') return anchor;
      return _origCreateElement(tagName, options) as HTMLElement;
    },
  );
  return spy;
}

describe('ExportButton', () => {
  let createObjectURLSpy: ReturnType<typeof vi.spyOn>;
  let revokeObjectURLSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    createObjectURLSpy = vi
      .spyOn(URL, 'createObjectURL')
      .mockReturnValue('blob:mock-url');
    revokeObjectURLSpy = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── rendering ─────────────────────────────────────────────────────

  it('renders Export PNG button', () => {
    const chartRef = makeChartRef();
    render(<ExportButton chartRef={chartRef} chartLabel="Test Chart" />);

    const pngBtn = screen.getByRole('button', { name: 'Export PNG' });
    expect(pngBtn).toBeInTheDocument();
  });

  it('does not render CSV button when csvData is not provided', () => {
    const chartRef = makeChartRef();
    render(<ExportButton chartRef={chartRef} chartLabel="Test Chart" />);

    expect(screen.queryByRole('button', { name: 'Export CSV' })).not.toBeInTheDocument();
  });

  it('does not render CSV button when csvData is null', () => {
    const chartRef = makeChartRef();
    render(
      <ExportButton chartRef={chartRef} chartLabel="Test Chart" csvData={null} />,
    );

    expect(screen.queryByRole('button', { name: 'Export CSV' })).not.toBeInTheDocument();
  });

  it('renders Export CSV button when csvData is provided', () => {
    const chartRef = makeChartRef();
    const csvData = makeCsvData(['A', 'B'], [['1', '2']]);

    render(
      <ExportButton chartRef={chartRef} chartLabel="Test Chart" csvData={csvData} />,
    );

    const csvBtn = screen.getByRole('button', { name: 'Export CSV' });
    expect(csvBtn).toBeInTheDocument();
  });

  it('renders both buttons when csvData is provided', () => {
    const chartRef = makeChartRef();
    const csvData = makeCsvData(['A'], [['1']]);

    render(
      <ExportButton chartRef={chartRef} chartLabel="Test Chart" csvData={csvData} />,
    );

    const buttons = screen.getAllByRole('button');
    expect(buttons).toHaveLength(2);
    expect(buttons[0]).toHaveTextContent('Export PNG');
    expect(buttons[1]).toHaveTextContent('Export CSV');
  });

  // ── button types (CR-007 regression) ─────────────────────────────

  it('PNG button has type="button"', () => {
    const chartRef = makeChartRef();
    render(<ExportButton chartRef={chartRef} chartLabel="Test Chart" />);

    const pngBtn = screen.getByRole('button', { name: 'Export PNG' });
    expect(pngBtn).toHaveAttribute('type', 'button');
  });

  it('CSV button has type="button"', () => {
    const chartRef = makeChartRef();
    const csvData = makeCsvData(['A'], [['1']]);

    render(
      <ExportButton chartRef={chartRef} chartLabel="Test Chart" csvData={csvData} />,
    );

    const csvBtn = screen.getByRole('button', { name: 'Export CSV' });
    expect(csvBtn).toHaveAttribute('type', 'button');
  });

  // ── PNG export behavior ──────────────────────────────────────────

  it('calls getDataURL with correct options on PNG button click', () => {
    const chartRef = makeChartRef();

    // Stub anchor creation so click() doesn't navigate
    const anchor = document.createElement('a');
    vi.spyOn(anchor, 'click');
    mockCreateElement(anchor);

    render(<ExportButton chartRef={chartRef} chartLabel="Test Chart" />);

    const pngBtn = screen.getByRole('button', { name: 'Export PNG' });
    fireEvent.click(pngBtn);

    expect(chartRef.current?.getDataURL).toHaveBeenCalledWith({
      type: 'png',
      pixelRatio: 2,
      backgroundColor: '#fff',
    });
  });

  it('triggers download with correct PNG filename on click', () => {
    const chartRef = makeChartRef();
    const anchor = document.createElement('a');
    const clickSpy = vi.spyOn(anchor, 'click');
    mockCreateElement(anchor);

    render(<ExportButton chartRef={chartRef} chartLabel="My UoP Chart" />);

    const pngBtn = screen.getByRole('button', { name: 'Export PNG' });
    fireEvent.click(pngBtn);

    expect(anchor.download).toBe('My_UoP_Chart.png');
    expect(clickSpy).toHaveBeenCalled();
  });

  it('does nothing on PNG click when chartRef.current is null', () => {
    const chartRef: RefObject<EChartsType | null> = { current: null };
    render(<ExportButton chartRef={chartRef} chartLabel="Test Chart" />);

    const pngBtn = screen.getByRole('button', { name: 'Export PNG' });
    // Should not throw
    expect(() => fireEvent.click(pngBtn)).not.toThrow();
  });

  // ── CSV export behavior ──────────────────────────────────────────

  it('creates Blob with correct CSV content on CSV button click', () => {
    const BlobSpy = vi.spyOn(globalThis, 'Blob');
    const chartRef = makeChartRef();
    const csvData = makeCsvData(['Name', 'Value'], [['Alice', '100'], ['Bob', '200']]);

    const anchor = document.createElement('a');
    vi.spyOn(anchor, 'click');
    mockCreateElement(anchor);

    render(
      <ExportButton chartRef={chartRef} chartLabel="Test Chart" csvData={csvData} />,
    );

    const csvBtn = screen.getByRole('button', { name: 'Export CSV' });
    fireEvent.click(csvBtn);

    expect(BlobSpy).toHaveBeenCalledWith(
      ['"Name","Value"\n"Alice","100"\n"Bob","200"'],
      { type: 'text/csv' },
    );
  });

  it('triggers download with correct CSV filename on click', () => {
    const chartRef = makeChartRef();
    const csvData = makeCsvData(['A'], [['1']]);

    const anchor = document.createElement('a');
    const clickSpy = vi.spyOn(anchor, 'click');
    mockCreateElement(anchor);

    render(
      <ExportButton chartRef={chartRef} chartLabel="My CSV Report" csvData={csvData} />,
    );

    const csvBtn = screen.getByRole('button', { name: 'Export CSV' });
    fireEvent.click(csvBtn);

    expect(anchor.download).toBe('My_CSV_Report.csv');
    expect(clickSpy).toHaveBeenCalled();
  });

  it('calls revokeObjectURL even when triggerDownload throws (CR-011)', () => {
    const chartRef = makeChartRef();
    const csvData = makeCsvData(['A'], [['1']]);

    // Make document.createElement return an anchor whose click() throws
    const anchor = document.createElement('a');
    vi.spyOn(anchor, 'click').mockImplementation(() => {
      throw new Error('CSP violation');
    });
    mockCreateElement(anchor);

    render(
      <ExportButton chartRef={chartRef} chartLabel="Test Chart" csvData={csvData} />,
    );

    const csvBtn = screen.getByRole('button', { name: 'Export CSV' });
    fireEvent.click(csvBtn);

    // revokeObjectURL must be called even after the error (cleanup in finally)
    expect(revokeObjectURLSpy).toHaveBeenCalledWith('blob:mock-url');
  });

  it('calls createObjectURL and revokeObjectURL on CSV export', () => {
    const chartRef = makeChartRef();
    const csvData = makeCsvData(['A'], [['1']]);

    const anchor = document.createElement('a');
    vi.spyOn(anchor, 'click');
    mockCreateElement(anchor);

    render(
      <ExportButton chartRef={chartRef} chartLabel="Test Chart" csvData={csvData} />,
    );

    const csvBtn = screen.getByRole('button', { name: 'Export CSV' });
    fireEvent.click(csvBtn);

    expect(createObjectURLSpy).toHaveBeenCalledOnce();
    expect(revokeObjectURLSpy).toHaveBeenCalledWith('blob:mock-url');
  });

  it('CSV button absent when csvData is undefined (only PNG renders)', () => {
    const chartRef = makeChartRef();
    render(<ExportButton chartRef={chartRef} chartLabel="Test Chart" />);

    const buttons = screen.getAllByRole('button');
    expect(buttons).toHaveLength(1);
    expect(buttons[0]).toHaveTextContent('Export PNG');
  });

  // ── filename sanitization (CR-010) ───────────────────────────────

  it('sanitizes PNG filename with Windows-forbidden characters', () => {
    const chartRef = makeChartRef();
    const anchor = document.createElement('a');
    const clickSpy = vi.spyOn(anchor, 'click');
    mockCreateElement(anchor);

    render(<ExportButton chartRef={chartRef} chartLabel="Q1/Q2: Revenue * Analysis?" />);

    const pngBtn = screen.getByRole('button', { name: 'Export PNG' });
    fireEvent.click(pngBtn);

    expect(anchor.download).toBe('Q1_Q2__Revenue___Analysis_.png');
    expect(clickSpy).toHaveBeenCalled();
  });

  it('sanitizes CSV filename with Windows-forbidden characters', () => {
    const chartRef = makeChartRef();
    const csvData = makeCsvData(['A'], [['1']]);

    const anchor = document.createElement('a');
    const clickSpy = vi.spyOn(anchor, 'click');
    mockCreateElement(anchor);

    render(
      <ExportButton chartRef={chartRef} chartLabel="Report <Critical>|Important" csvData={csvData} />,
    );

    const csvBtn = screen.getByRole('button', { name: 'Export CSV' });
    fireEvent.click(csvBtn);

    expect(anchor.download).toBe('Report__Critical__Important.csv');
    expect(clickSpy).toHaveBeenCalled();
  });

  // ── layout ───────────────────────────────────────────────────────

  it('renders buttons with flex layout container', () => {
    const chartRef = makeChartRef();
    const csvData = makeCsvData(['A'], [['1']]);

    const { container } = render(
      <ExportButton chartRef={chartRef} chartLabel="Test Chart" csvData={csvData} />,
    );

    const root = container.firstElementChild as HTMLElement;
    expect(root).not.toBeNull();
    expect(root.style.display).toBe('flex');
    expect(root.style.gap).toBe('8px');
  });
});
