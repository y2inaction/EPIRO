import { render, screen } from '@testing-library/react'
import Home from '@/app/page'

describe('Home Page', () => {
  it('renders the EPIRO title', () => {
    render(<Home />)
    const title = screen.getByText(/EPIRO/i)
    expect(title).toBeInTheDocument()
  })

  it('has navigation links', () => {
    render(<Home />)
    const dashboardLink = screen.getByText(/Dashboard/i)
    const loginLink = screen.getByText(/Login/i)
    expect(dashboardLink).toBeInTheDocument()
    expect(loginLink).toBeInTheDocument()
  })
})
