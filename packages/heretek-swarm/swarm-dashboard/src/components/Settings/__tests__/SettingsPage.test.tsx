/**
 * SettingsPage — Tier 1.1 regression test
 *
 * Verifies that the "Save API Key" button actually persists the value to
 * localStorage (regression for the day-one bug where the button only fired
 * a toast).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import React from 'react';

vi.mock('../../../components/UI/Toast', async () => {
  const actual = await vi.importActual<typeof import('../../../components/UI/Toast')>(
    '../../../components/UI/Toast',
  );
  return {
    ...actual,
    useToast: () => ({
      success: vi.fn(),
      info: vi.fn(),
      error: vi.fn(),
    }),
  };
});

import { SettingsPage } from '../SettingsPage';
import { ToastProvider } from '../../../components/UI/Toast';

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  cleanup();
  localStorage.clear();
});

describe('SettingsPage — Save API Key', () => {
  it('persists the API key to localStorage when Save is clicked', () => {
    render(
      <ToastProvider>
        <SettingsPage />
      </ToastProvider>,
    );
    const input = screen.getByPlaceholderText('Enter your API key') as HTMLInputElement;
    const saveBtn = screen.getAllByText('Save')[0] as HTMLButtonElement;

    fireEvent.change(input, { target: { value: 'htsk_test_abc123' } });
    fireEvent.click(saveBtn);

    expect(localStorage.getItem('api_key')).toBe('htsk_test_abc123');
  });
});
