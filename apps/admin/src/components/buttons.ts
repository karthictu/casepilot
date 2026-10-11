// Shared Tailwind class strings for buttons, so every page uses the same look.

const base =
  'inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500 disabled:cursor-not-allowed disabled:opacity-50'

export const buttonPrimary = `${base} bg-indigo-600 text-white shadow-sm hover:bg-indigo-500`
export const buttonSecondary = `${base} bg-white text-slate-700 shadow-sm ring-1 ring-inset ring-slate-300 hover:bg-slate-50`
export const buttonSuccess = `${base} bg-emerald-600 text-white shadow-sm hover:bg-emerald-500`
export const buttonDanger = `${base} bg-white text-rose-700 shadow-sm ring-1 ring-inset ring-rose-300 hover:bg-rose-50`
export const buttonSmall = 'px-2.5 py-1 text-xs'

export const inputClass =
  'block rounded-lg border-0 bg-white px-2.5 py-1.5 text-sm text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 placeholder:text-slate-400 focus:ring-2 focus:ring-indigo-500 focus:outline-none'
