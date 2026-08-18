import React from 'react';
import { render, screen } from '@testing-library/react';
import App from './App';

test('renders the File Vault System heading', () => {
  render(<App />);
  const heading = screen.getByText(/File Vault System/i);
  expect(heading).toBeInTheDocument();
});
