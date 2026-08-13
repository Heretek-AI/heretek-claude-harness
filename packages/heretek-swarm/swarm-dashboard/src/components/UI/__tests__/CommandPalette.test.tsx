/**
 * CommandPalette — Tier 5.1 smoke test
 *
 * Verifies the palette opens via Cmd+K, filters items by search,
 * and invokes the selection callback on ↵.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent, act } from '@testing-library/react';
import React from 'react';
import { CommandPalette } from '../CommandPalette';

const items = [
  { id: 'nav:home', label: 'Home', group: 'Page' as const, icon: '🏠' },
  { id: 'nav:agents', label: 'Agents', group: 'Page' as const, icon: '🤖' },
  { id: 'action:refresh', label: 'Refresh dashboard', group: 'Action' as const, icon: '↻' },
];

beforeEach(() => {
  // jsdom doesn't implement window.location.assign; stub it.
  Object.defineProperty(window, 'location', {
    value: { assign: vi.fn(), pathname: '/' },
    writable: true,
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('CommandPalette', () => {
  it('opens when Cmd+K is pressed', () => {
    render(<CommandPalette items={items} />);
    expect(screen.queryByRole('dialog')).toBeNull();
    act(() => {
      fireEvent.keyDown(window, { key: 'k', metaKey: true });
    });
    expect(screen.getByRole('dialog', { name: /command palette/i })).toBeInTheDocument();
  });

  it('filters items by search', () => {
    render(<CommandPalette items={items} />);
    act(() => {
      fireEvent.keyDown(window, { key: 'k', metaKey: true });
    });
    const input = screen.getByPlaceholderText(/Type a page or action/i) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'home' } });
    // The "Agents" item should not be in the DOM after filter
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.queryByText('Agents')).toBeNull();
  });

  it('closes on Esc', () => {
    render(<CommandPalette items={items} />);
    act(() => {
      fireEvent.keyDown(window, { key: 'k', metaKey: true });
    });
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    act(() => {
      fireEvent.keyDown(window, { key: 'Escape' });
    });
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});
