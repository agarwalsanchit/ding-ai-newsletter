'use client';

import { useState, useEffect, useCallback } from 'react';

const KEY = 'ding_topic_prefs';

function stripEmoji(topic: string): string {
  return topic.split(' ').slice(1).join(' ');
}

export function useTopicPrefs(allTopics: string[]) {
  // null means "all selected" (default); a Set means explicit selection
  const [selected, setSelected] = useState<Set<string> | null>(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as string[];
        // If user had all topics selected explicitly, treat as null (all)
        if (parsed.length === allTopics.length) {
          setSelected(null);
        } else {
          setSelected(new Set(parsed));
        }
      }
    } catch {
      // ignore parse errors
    }
  }, [allTopics.length]);

  const toggle = useCallback((topic: string) => {
    setSelected((prev) => {
      const base = prev ?? new Set(allTopics);
      const next = new Set(base);
      if (next.has(topic)) {
        next.delete(topic);
      } else {
        next.add(topic);
      }
      // If all are selected, persist as null
      if (next.size === allTopics.length) {
        localStorage.removeItem(KEY);
        return null;
      }
      localStorage.setItem(KEY, JSON.stringify([...next]));
      return next;
    });
  }, [allTopics]);

  const selectAll = useCallback(() => {
    localStorage.removeItem(KEY);
    setSelected(null);
  }, []);

  const isSelected = useCallback(
    (topic: string) => selected === null || selected.has(topic),
    [selected]
  );

  const activeCount = selected === null ? allTopics.length : selected.size;

  return { isSelected, toggle, selectAll, activeCount, stripEmoji };
}
