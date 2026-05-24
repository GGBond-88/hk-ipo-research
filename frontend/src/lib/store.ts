import { create } from 'zustand';

export interface FilterState {
  year: string | null;
  industry: string | null;
  country: string | null;
  parent: string | null;
  commitment: string | null;
}

export interface AppState extends FilterState {
  setFilter: <K extends keyof FilterState>(key: K, value: FilterState[K]) => void;
  resetFilters: () => void;
  activeTicker: string | null;
  setActiveTicker: (ticker: string | null) => void;
}

const initialFilters: FilterState = {
  year: null,
  industry: null,
  country: null,
  parent: null,
  commitment: null,
};

export const useStore = create<AppState>((set) => ({
  ...initialFilters,
  setFilter: (key, value) => set({ [key]: value }),
  resetFilters: () => set(initialFilters),
  activeTicker: null,
  setActiveTicker: (ticker) => set({ activeTicker: ticker }),
}));
