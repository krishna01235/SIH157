import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('app shell', () => {
  it('identifies the product', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: 'NIGRANI-SA' })).toBeTruthy()
  })
})
