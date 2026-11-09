// src/hooks/use-debounce.ts
// FR-DC-011: search-as-you-type debounces at ≥300ms. Returns the debounced
// value; consumers keep their own keyboard navigation state.

import { useEffect, useState } from "react"

export function useDebounce<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])
  return debounced
}
