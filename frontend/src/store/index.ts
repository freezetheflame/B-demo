import { create } from 'zustand'

interface FormState {
  // Filters
  filterFormType: string
  filterStatus: string
  filterKeyword: string
  filterGeohash: string
  page: number
  pageSize: number

  // Actions
  setFilter: (key: string, value: string) => void
  setPage: (page: number) => void
  reset: () => void
}

export const useFormStore = create<FormState>((set) => ({
  filterFormType: 'merchant',
  filterStatus: '',
  filterKeyword: '',
  filterGeohash: '',
  page: 1,
  pageSize: 50,

  setFilter: (key, value) => set({ [key]: value, page: 1 }),
  setPage: (page) => set({ page }),
  reset: () => set({
    filterFormType: 'merchant', filterStatus: '', filterKeyword: '',
    filterGeohash: '', page: 1,
  }),
}))
