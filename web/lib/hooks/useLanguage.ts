'use client';

import { useState, useEffect } from 'react';

export type Language = 'en' | 'hi';

const KEY = 'ding_language';

export function useLanguage() {
  const [lang, setLang] = useState<Language>('en');

  useEffect(() => {
    const stored = localStorage.getItem(KEY) as Language | null;
    if (stored === 'hi') setLang('hi');
  }, []);

  const toggle = () => {
    setLang((prev) => {
      const next: Language = prev === 'en' ? 'hi' : 'en';
      localStorage.setItem(KEY, next);
      return next;
    });
  };

  return { lang, toggle };
}
