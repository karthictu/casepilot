import { createContext, useContext } from 'react'

export type ToastTone = 'info' | 'success' | 'warning' | 'error'

export interface ToastInput {
  title: string
  description?: string
  tone?: ToastTone
}

export interface Toast extends Required<Omit<ToastInput, 'description'>> {
  id: number
  description?: string
}

export interface ToastApi {
  notify: (toast: ToastInput) => void
}

export const ToastContext = createContext<ToastApi | null>(null)

/** Show transient notifications. Falls back to a no-op outside a ToastProvider. */
export function useToast(): ToastApi {
  return useContext(ToastContext) ?? { notify: () => {} }
}
