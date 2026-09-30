import { describe, expect, it } from 'vitest'
import { formatWindow, parseUtc } from './api'

describe('UTC reporting window', () => {
  it('treats SQLite timestamps without an offset as UTC', () => {
    expect(parseUtc('2026-01-01T00:00:00').toISOString()).toBe('2026-01-01T00:00:00.000Z')
    expect(formatWindow('2026-01-01T00:00:00', '2026-01-08T00:00:00')).toBe('01 Jan 2026 – 07 Jan 2026')
  })
})
