import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { FilterBar } from '../FilterBar';
import { useStore } from '../../lib/store';
import type { FilterOptions } from '../../lib/filterOptions';

function makeOptions(overrides: Partial<FilterOptions> = {}): FilterOptions {
  return {
    years: ['2023', '2024', '2025'],
    industries: ['Finance', 'Healthcare', 'Technology'],
    countries: ['CN', 'JP', 'US'],
    parents: ['Financing', 'Growth', 'Others', 'Working Capital'],
    commitments: ['committed', 'discretionary'],
    ...overrides,
  };
}

describe('FilterBar', () => {
  beforeEach(() => {
    // Reset the Zustand store to initial state before each test
    useStore.setState({
      year: null,
      industry: null,
      country: null,
      parent: null,
      commitment: null,
      activeTicker: null,
    });
  });

  // ── dropdown rendering ───────────────────────────────────────────

  it('renders all 5 filter dropdowns with labels', () => {
    render(<FilterBar options={makeOptions()} />);

    expect(screen.getByText('Year:')).toBeInTheDocument();
    expect(screen.getByText('Industry:')).toBeInTheDocument();
    expect(screen.getByText('Country:')).toBeInTheDocument();
    expect(screen.getByText('Parent:')).toBeInTheDocument();
    expect(screen.getByText('Commitment:')).toBeInTheDocument();
  });

  it('renders option values for each dropdown', () => {
    render(<FilterBar options={makeOptions()} />);

    const selects = screen.getAllByRole('combobox');
    expect(selects).toHaveLength(5);

    // Check that each select has an "All" option plus its data options
    const yearSelect = selects[0] as HTMLSelectElement;
    expect(yearSelect.options).toHaveLength(1 + 3); // All + 3 years
    expect(yearSelect.options[0].textContent).toBe('All');
    expect(yearSelect.options[1].textContent).toBe('2023');

    const industrySelect = selects[1] as HTMLSelectElement;
    expect(industrySelect.options).toHaveLength(1 + 3); // All + 3 industries
    expect(industrySelect.options[1].textContent).toBe('Finance');
  });

  it('renders "All" options selected by default', () => {
    render(<FilterBar options={makeOptions()} />);

    const selects = screen.getAllByRole('combobox') as HTMLSelectElement[];
    for (const select of selects) {
      expect(select.value).toBe('');
    }
  });

  it('updates select values when store has active filters', () => {
    useStore.setState({ year: '2024', industry: 'Technology' });
    render(<FilterBar options={makeOptions()} />);

    const selects = screen.getAllByRole('combobox') as HTMLSelectElement[];
    expect(selects[0].value).toBe('2024');
    expect(selects[1].value).toBe('Technology');
  });

  // ── setFilter interactions ────────────────────────────────────────

  it('calls setFilter when a dropdown value changes', () => {
    const setFilterSpy = vi.spyOn(useStore.getState(), 'setFilter');
    render(<FilterBar options={makeOptions()} />);

    const selects = screen.getAllByRole('combobox') as HTMLSelectElement[];
    fireEvent.change(selects[0], { target: { value: '2023' } });

    expect(setFilterSpy).toHaveBeenCalledWith('year', '2023');
    setFilterSpy.mockRestore();
  });

  it('calls setFilter with null when "All" is selected', () => {
    // First set a value so we can switch back to "All"
    useStore.setState({ year: '2023' });
    const setFilterSpy = vi.spyOn(useStore.getState(), 'setFilter');
    render(<FilterBar options={makeOptions()} />);

    const selects = screen.getAllByRole('combobox') as HTMLSelectElement[];
    fireEvent.change(selects[0], { target: { value: '' } });

    expect(setFilterSpy).toHaveBeenCalledWith('year', null);
    setFilterSpy.mockRestore();
  });

  it('updates industry filter via dropdown change', () => {
    const setFilterSpy = vi.spyOn(useStore.getState(), 'setFilter');
    render(<FilterBar options={makeOptions()} />);

    const selects = screen.getAllByRole('combobox') as HTMLSelectElement[];
    fireEvent.change(selects[1], { target: { value: 'Healthcare' } });

    expect(setFilterSpy).toHaveBeenCalledWith('industry', 'Healthcare');
    setFilterSpy.mockRestore();
  });

  it('updates country filter via dropdown change', () => {
    const setFilterSpy = vi.spyOn(useStore.getState(), 'setFilter');
    render(<FilterBar options={makeOptions()} />);

    const selects = screen.getAllByRole('combobox') as HTMLSelectElement[];
    fireEvent.change(selects[2], { target: { value: 'JP' } });

    expect(setFilterSpy).toHaveBeenCalledWith('country', 'JP');
    setFilterSpy.mockRestore();
  });

  it('updates parent filter via dropdown change', () => {
    const setFilterSpy = vi.spyOn(useStore.getState(), 'setFilter');
    render(<FilterBar options={makeOptions()} />);

    const selects = screen.getAllByRole('combobox') as HTMLSelectElement[];
    fireEvent.change(selects[3], { target: { value: 'Working Capital' } });

    expect(setFilterSpy).toHaveBeenCalledWith('parent', 'Working Capital');
    setFilterSpy.mockRestore();
  });

  it('updates commitment filter via dropdown change', () => {
    const setFilterSpy = vi.spyOn(useStore.getState(), 'setFilter');
    render(<FilterBar options={makeOptions()} />);

    const selects = screen.getAllByRole('combobox') as HTMLSelectElement[];
    fireEvent.change(selects[4], { target: { value: 'discretionary' } });

    expect(setFilterSpy).toHaveBeenCalledWith('commitment', 'discretionary');
    setFilterSpy.mockRestore();
  });

  // ── Reset Filters button ───────────────────────────────────────────

  it('renders Reset Filters button', () => {
    render(<FilterBar options={makeOptions()} />);

    const resetBtn = screen.getByRole('button', { name: 'Reset Filters' });
    expect(resetBtn).toBeInTheDocument();
  });

  it('Reset button has type="button"', () => {
    render(<FilterBar options={makeOptions()} />);

    const resetBtn = screen.getByRole('button', { name: 'Reset Filters' });
    expect(resetBtn).toHaveAttribute('type', 'button');
  });

  it('calls resetFilters when Reset button is clicked', () => {
    const resetFiltersSpy = vi.spyOn(useStore.getState(), 'resetFilters');
    render(<FilterBar options={makeOptions()} />);

    const resetBtn = screen.getByRole('button', { name: 'Reset Filters' });
    fireEvent.click(resetBtn);

    expect(resetFiltersSpy).toHaveBeenCalledOnce();
    resetFiltersSpy.mockRestore();
  });

  it('clears active filters when Reset is clicked after selecting values', () => {
    useStore.setState({ year: '2024', industry: 'Technology' });
    render(<FilterBar options={makeOptions()} />);

    const resetBtn = screen.getByRole('button', { name: 'Reset Filters' });
    fireEvent.click(resetBtn);

    const state = useStore.getState();
    expect(state.year).toBeNull();
    expect(state.industry).toBeNull();
  });

  // ── ticker picker rendering ────────────────────────────────────────

  it('does not render ticker picker when showTickerPicker is not set', () => {
    render(<FilterBar options={makeOptions()} />);

    expect(screen.queryByText('Company:')).not.toBeInTheDocument();
  });

  it('does not render ticker picker when showTickerPicker=true but tickers is undefined', () => {
    render(<FilterBar options={makeOptions()} showTickerPicker={true} />);

    expect(screen.queryByText('Company:')).not.toBeInTheDocument();
  });

  it('does not render ticker picker when tickers array is empty', () => {
    render(
      <FilterBar options={makeOptions()} showTickerPicker={true} tickers={[]} />,
    );

    expect(screen.queryByText('Company:')).not.toBeInTheDocument();
  });

  it('renders ticker picker when showTickerPicker=true and tickers has items', () => {
    const tickers = [
      { hk_ticker: '00001', company_name_en: 'Alpha Corp' },
      { hk_ticker: '00002', company_name_en: 'Beta Ltd' },
    ];

    render(
      <FilterBar options={makeOptions()} showTickerPicker={true} tickers={tickers} />,
    );

    expect(screen.getByText('Company:')).toBeInTheDocument();

    // Check ticker options are rendered
    const tickerSelect = screen.getAllByRole('combobox')[5] as HTMLSelectElement;
    expect(tickerSelect.options).toHaveLength(1 + 2); // placeholder + 2 tickers
    expect(tickerSelect.options[1].textContent).toBe('00001 - Alpha Corp');
    expect(tickerSelect.options[2].textContent).toBe('00002 - Beta Ltd');
  });

  it('calls setActiveTicker when ticker picker value changes', () => {
    const setActiveTickerSpy = vi.spyOn(useStore.getState(), 'setActiveTicker');
    const tickers = [
      { hk_ticker: '00001', company_name_en: 'Alpha Corp' },
      { hk_ticker: '00002', company_name_en: 'Beta Ltd' },
    ];

    render(
      <FilterBar options={makeOptions()} showTickerPicker={true} tickers={tickers} />,
    );

    const tickerSelect = screen.getAllByRole('combobox')[5] as HTMLSelectElement;
    fireEvent.change(tickerSelect, { target: { value: '00001' } });

    expect(setActiveTickerSpy).toHaveBeenCalledWith('00001');
    setActiveTickerSpy.mockRestore();
  });

  it('calls setActiveTicker with null when ticker picker selects placeholder', () => {
    useStore.setState({ activeTicker: '00001' });
    const setActiveTickerSpy = vi.spyOn(useStore.getState(), 'setActiveTicker');
    const tickers = [
      { hk_ticker: '00001', company_name_en: 'Alpha Corp' },
    ];

    render(
      <FilterBar options={makeOptions()} showTickerPicker={true} tickers={tickers} />,
    );

    const tickerSelect = screen.getAllByRole('combobox')[5] as HTMLSelectElement;
    fireEvent.change(tickerSelect, { target: { value: '' } });

    expect(setActiveTickerSpy).toHaveBeenCalledWith(null);
    setActiveTickerSpy.mockRestore();
  });

  // ── toSelectItems behavior (black-box via rendering) ───────────────

  it('renders options with matching value and label from toSelectItems', () => {
    render(<FilterBar options={makeOptions({ years: ['2024'] })} />);

    const yearSelect = screen.getAllByRole('combobox')[0] as HTMLSelectElement;
    expect(yearSelect.options[1].value).toBe('2024');
    expect(yearSelect.options[1].textContent).toBe('2024');
  });

  it('hides dropdown when its option list is empty (CR-004)', () => {
    // When years is empty, the Year dropdown should not render
    render(<FilterBar options={makeOptions({ years: [] })} />);

    // Year label should NOT be in the document
    expect(screen.queryByText('Year:')).not.toBeInTheDocument();
    // The other 4 dropdowns should still render
    expect(screen.getByText('Industry:')).toBeInTheDocument();
    expect(screen.getByText('Country:')).toBeInTheDocument();
    expect(screen.getByText('Parent:')).toBeInTheDocument();
    expect(screen.getByText('Commitment:')).toBeInTheDocument();
  });

  it('hides all filter dropdowns when all option lists are empty', () => {
    render(<FilterBar options={makeOptions({ years: [], industries: [], countries: [], parents: [], commitments: [] })} />);

    // No filter dropdown labels should appear
    expect(screen.queryByText('Year:')).not.toBeInTheDocument();
    expect(screen.queryByText('Industry:')).not.toBeInTheDocument();
    expect(screen.queryByText('Country:')).not.toBeInTheDocument();
    expect(screen.queryByText('Parent:')).not.toBeInTheDocument();
    expect(screen.queryByText('Commitment:')).not.toBeInTheDocument();
    // Reset Filters button should still be present
    expect(screen.getByRole('button', { name: 'Reset Filters' })).toBeInTheDocument();
    // No comboboxes should render (since no dropdowns and no ticker picker)
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
  });

  // ── layout and styling ────────────────────────────────────────────

  it('renders with flex layout container', () => {
    const { container } = render(<FilterBar options={makeOptions()} />);

    const root = container.firstElementChild as HTMLElement;
    expect(root).not.toBeNull();
    expect(root.style.display).toBe('flex');
    expect(root.style.flexWrap).toBe('wrap');
    expect(root.style.gap).toBe('12px');
  });
});
