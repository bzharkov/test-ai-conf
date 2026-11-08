import { useSyncExternalStore } from "react";
import type { ConfigureResponse } from "../api/types";

function safeGet(key: string, storage: Storage | undefined): string | null {
  try {
    return storage?.getItem(key) ?? null;
  } catch {
    return null;
  }
}
function safeSet(key: string, value: string, storage: Storage | undefined) {
  try {
    storage?.setItem(key, value);
  } catch {
    /* private mode */
  }
}

const ls = typeof window !== "undefined" ? window.localStorage : undefined;
const ss = typeof window !== "undefined" ? window.sessionStorage : undefined;

export function getSessionId(): string {
  let id = safeGet("pcconf_session", ls);
  if (!id) {
    id = (
      globalThis.crypto?.randomUUID?.() ?? `s${Date.now()}${Math.random().toString(36).slice(2)}`
    )
      .replace(/-/g, "")
      .slice(0, 32);
    safeSet("pcconf_session", id, ls);
  }
  return id;
}

/* tiny external store: compare list + last result, shared between pages */
type Listener = () => void;
const listeners = new Set<Listener>();
const emit = () => listeners.forEach((l) => l());
const subscribe = (l: Listener) => {
  listeners.add(l);
  return () => listeners.delete(l);
};

let compareIds: number[] = JSON.parse(safeGet("pcconf_compare", ls) ?? "[]");
let compareSnapshot = compareIds;

export function toggleCompare(id: number) {
  compareIds = compareIds.includes(id)
    ? compareIds.filter((x) => x !== id)
    : [...compareIds, id].slice(-3);
  compareSnapshot = compareIds;
  safeSet("pcconf_compare", JSON.stringify(compareIds), ls);
  emit();
}

export function useCompareIds(): number[] {
  return useSyncExternalStore(subscribe, () => compareSnapshot);
}

let last: { text: string; data: ConfigureResponse } | null = JSON.parse(
  safeGet("pcconf_last", ss) ?? "null",
);

export function setLastResult(v: { text: string; data: ConfigureResponse } | null) {
  last = v;
  safeSet("pcconf_last", JSON.stringify(v), ss);
  emit();
}

export function useLastResult() {
  return useSyncExternalStore(subscribe, () => last);
}
