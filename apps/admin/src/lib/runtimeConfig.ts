import type { RuntimeConfig } from '../api/types'
import type { BadgeTone } from './status'

export interface ConfigBadge {
  key: string
  label: string
  value: string
  tone: BadgeTone
  hint: string
}

export function configBadges(config: RuntimeConfig): ConfigBadge[] {
  return [
    {
      key: 'write_mode',
      label: 'Writes',
      value: config.write_mode,
      tone: config.write_mode === 'live' ? 'rose' : 'amber',
      hint:
        config.write_mode === 'live'
          ? 'Live: approved actions change real bookings'
          : 'Shadow: cases are processed, but nothing is written to the booking backend',
    },
    {
      key: 'llm_provider',
      label: 'LLM',
      value: config.llm_provider,
      tone: config.llm_provider === 'mock' ? 'slate' : 'indigo',
      hint: 'Model provider used for classification, extraction and chat',
    },
    {
      key: 'agent_runtime',
      label: 'Runtime',
      value: config.agent_runtime,
      tone: 'indigo',
      hint: 'Agent runtime that executes agent turns',
    },
    {
      key: 'temporal',
      label: 'Temporal',
      value: config.temporal_enabled ? 'on' : 'off',
      tone: config.temporal_enabled ? 'emerald' : 'slate',
      hint: config.temporal_enabled
        ? 'Case processing and approvals run as durable workflows'
        : 'Case processing runs in-process',
    },
  ]
}
