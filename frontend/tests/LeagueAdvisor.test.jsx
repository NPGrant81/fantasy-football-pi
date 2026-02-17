import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi } from 'vitest'

vi.mock('../src/api/client', () => ({ default: { post: vi.fn() } }))
import apiClient from '../src/api/client'
import LeagueAdvisor from '../src/components/LeagueAdvisor'

describe('LeagueAdvisor (chat)', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  test('opens on toggle and sends message, displays AI response', async () => {
    apiClient.post.mockResolvedValue({ data: { response: 'Hello from AI' } })
    render(<LeagueAdvisor />)

    // Toggle open
    const toggle = screen.getByRole('button', { name: /🤖/i })
    fireEvent.click(toggle)

    // Type a message into the input
    const input = await screen.findByPlaceholderText(/Search players or ask advice/i)
    fireEvent.change(input, { target: { value: 'Who should I draft?' } })

    // Click send
    const sendBtn = screen.getByRole('button', { name: '' }) // icon button
    fireEvent.click(sendBtn)

    await waitFor(() => expect(apiClient.post).toHaveBeenCalledWith('/advisor/ask', { user_query: 'Who should I draft?' }))
    expect(await screen.findByText(/Hello from AI/i)).toBeInTheDocument()
  })
})
