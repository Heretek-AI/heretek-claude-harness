/**
 * Command Palette (Tier 5.1)
 *
 * Global Cmd+K / "/" palette over the dashboard's nav items,
 * agents, and providers. Fuzzy-matches on label / id. Selecting
 * an item navigates via the same path the sidebar uses
 * (window.location.assign), so the URL is the source of truth
 * (Tier 3) and the rest of the app's nav-click handler picks
 * up the new view.
 */

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Command } from 'cmdk';

export interface CommandItem {
  id: string;
  label: string;
  group: 'Page' | 'Action';
  icon?: string;
  shortcut?: string;
  keywords?: string[];
}

export interface CommandPaletteProps {
  items: CommandItem[];
}

export function CommandPalette({ items }: CommandPaletteProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  // Keyboard shortcut: Cmd+K (mac) / Ctrl+K (everything else) or "/".
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const isModK = (e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k';
      const isSlash = e.key === '/' && !['INPUT', 'TEXTAREA'].includes(
        (e.target as HTMLElement | null)?.tagName ?? '',
      );
      if (isModK || isSlash) {
        e.preventDefault();
        setOpen((prev) => !prev);
      } else if (e.key === 'Escape' && open) {
        setOpen(false);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open]);

  // Autofocus the input when the palette opens.
  useEffect(() => {
    if (open) {
      // Defer to next tick — the cmdk Command.Input mounts first.
      setTimeout(() => inputRef.current?.focus(), 0);
    } else {
      setSearch('');
    }
  }, [open]);

  const handleSelect = useCallback((id: string) => {
    setOpen(false);
    // Same path the sidebar uses; the app's existing nav-click
    // handler picks it up. Items whose id doesn't start with
    // "nav:" are treated as actions (no navigation).
    if (id.startsWith('nav:')) {
      const navId = id.slice(4);
      window.location.assign(`/${navId === 'home' ? '' : navId}`);
    }
  }, []);

  // Build the grouped list once per items / search.
  const grouped = useMemo(() => {
    const lc = search.toLowerCase();
    const filtered = items.filter((item) => {
      if (!lc) return true;
      return (
        item.label.toLowerCase().includes(lc) ||
        item.id.toLowerCase().includes(lc) ||
        item.keywords?.some((k) => k.toLowerCase().includes(lc))
      );
    });
    const groups: Record<string, CommandItem[]> = {};
    for (const item of filtered) {
      (groups[item.group] ??= []).push(item);
    }
    return groups;
  }, [items, search]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-24 bg-black/60 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
      onClick={(e) => {
        if (e.target === e.currentTarget) setOpen(false);
      }}
    >
      <div className="w-full max-w-lg bg-gray-900 border border-gray-700 rounded-lg shadow-2xl overflow-hidden">
        <Command shouldFilter={false} className="flex flex-col">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-700">
            <span className="text-gray-500">🔍</span>
            <Command.Input
              ref={inputRef}
              value={search}
              onValueChange={setSearch}
              placeholder="Type a page or action…"
              className="flex-1 bg-transparent text-white placeholder-gray-500 outline-none"
            />
            <kbd className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded">esc</kbd>
          </div>
          <Command.List className="max-h-80 overflow-y-auto p-2">
            <Command.Empty className="text-center text-gray-500 py-6">
              No results.
            </Command.Empty>
            {Object.entries(grouped).map(([group, list]) => (
              <Command.Group key={group} heading={group} className="text-xs text-gray-500 px-2 py-1">
                {list.map((item) => (
                  <Command.Item
                    key={item.id}
                    value={item.id}
                    onSelect={handleSelect}
                    className="flex items-center gap-3 px-3 py-2 rounded text-white cursor-pointer aria-selected:bg-blue-600 hover:bg-gray-800"
                  >
                    {item.icon && <span className="text-lg">{item.icon}</span>}
                    <span className="flex-1">{item.label}</span>
                    {item.shortcut && (
                      <kbd className="text-xs text-gray-400 bg-gray-800 px-2 py-0.5 rounded">
                        {item.shortcut}
                      </kbd>
                    )}
                  </Command.Item>
                ))}
              </Command.Group>
            ))}
          </Command.List>
          <div className="border-t border-gray-700 px-4 py-2 text-xs text-gray-500 flex items-center gap-3">
            <span>↑↓ navigate</span>
            <span>↵ select</span>
            <span>esc close</span>
          </div>
        </Command>
      </div>
    </div>
  );
}

export default CommandPalette;
