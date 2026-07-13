import { create } from "zustand";

export interface AccountUser {
  user_id: string;
  username: string;
}

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: AccountUser | null;
  setSession: (user: AccountUser, accessToken: string, refreshToken: string) => void;
  clearSession: () => void;
}

const storageKey = "coc-star.auth";

function loadSession(): Pick<AuthState, "accessToken" | "refreshToken" | "user"> {
  try {
    const stored = localStorage.getItem(storageKey);
    if (!stored) return { accessToken: null, refreshToken: null, user: null };
    return JSON.parse(stored) as Pick<AuthState, "accessToken" | "refreshToken" | "user">;
  } catch {
    return { accessToken: null, refreshToken: null, user: null };
  }
}

export const useAuthStore = create<AuthState>((set) => ({
  ...loadSession(),
  setSession: (user, accessToken, refreshToken) => {
    const session = { user, accessToken, refreshToken };
    localStorage.setItem(storageKey, JSON.stringify(session));
    set(session);
  },
  clearSession: () => {
    localStorage.removeItem(storageKey);
    set({ user: null, accessToken: null, refreshToken: null });
  },
}));
