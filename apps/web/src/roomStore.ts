import { create } from "zustand";

export type ConnectionStatus = "disconnected" | "connecting" | "connected" | "error";

export interface RoomMember {
  user_id: string;
  display_name: string;
  role: string;
}

export interface ChatMessage {
  message_id: string;
  user_id: string;
  display_name: string;
  text: string;
}

export interface BoardToken {
  token_id: string;
  owner_user_id: string;
  name: string;
  x: number;
  y: number;
  color: string;
}

interface RoomState {
  connectionStatus: ConnectionStatus;
  errorMessage: string | null;
  members: RoomMember[];
  messages: ChatMessage[];
  tokens: BoardToken[];
  roomId: string;
  self: RoomMember | null;
  setConnectionStatus: (connectionStatus: ConnectionStatus) => void;
  setRoomSnapshot: (roomId: string, self: RoomMember, members: RoomMember[]) => void;
  setBoardSnapshot: (tokens: BoardToken[]) => void;
  addMember: (member: RoomMember) => void;
  updateMember: (member: RoomMember) => void;
  removeMember: (userId: string) => void;
  addMessage: (message: ChatMessage) => void;
  upsertToken: (token: BoardToken) => void;
  removeToken: (tokenId: string) => void;
  setErrorMessage: (errorMessage: string | null) => void;
}

export const useRoomStore = create<RoomState>((set) => ({
  connectionStatus: "disconnected",
  errorMessage: null,
  members: [],
  messages: [],
  tokens: [],
  roomId: "demo-room",
  self: null,
  setConnectionStatus: (connectionStatus) => set({ connectionStatus }),
  setRoomSnapshot: (roomId, self, members) => set({ roomId, self, members, errorMessage: null }),
  setBoardSnapshot: (tokens) => set({ tokens }),
  addMember: (member) => set((state) => ({
    members: [...state.members.filter((current) => current.user_id !== member.user_id), member],
  })),
  updateMember: (member) => set((state) => ({
    members: state.members.map((current) => current.user_id === member.user_id ? member : current),
    self: state.self?.user_id === member.user_id ? member : state.self,
  })),
  removeMember: (userId) => set((state) => ({
    members: state.members.filter((member) => member.user_id !== userId),
  })),
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  upsertToken: (token) => set((state) => ({ tokens: [...state.tokens.filter((current) => current.token_id !== token.token_id), token] })),
  removeToken: (tokenId) => set((state) => ({ tokens: state.tokens.filter((token) => token.token_id !== tokenId) })),
  setErrorMessage: (errorMessage) => set({ errorMessage }),
}));
