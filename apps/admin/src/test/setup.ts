import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'
import { resetClientConfig } from '../api/client'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  resetClientConfig()
})
