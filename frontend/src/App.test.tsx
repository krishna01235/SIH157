import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'

describe('app shell', () => {
  it('identifies the product', () => {
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><BrowserRouter><App /></BrowserRouter></QueryClientProvider>)
    expect(screen.getByRole('heading', { level: 1, name: /Understand the SOC behind/ })).toBeTruthy()
  })
})
