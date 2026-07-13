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

export interface RoomScene {
  scene_id: string;
  name: string;
  background_url: string;
  is_active: boolean;
}

interface RoomState {
  connectionStatus: ConnectionStatus;
  errorMessage: string | null;
  members: RoomMember[];
  messages: ChatMessage[];
  tokens: BoardToken[];
  scenes: RoomScene[];
  activeScene: RoomScene | null;
  roomId: string;
  self: RoomMember | null;
  setConnectionStatus: (connectionStatus: ConnectionStatus) => void;
  setRoomSnapshot: (roomId: string, self: RoomMember, members: RoomMember[]) => void;
  setBoardSnapshot: (tokens: BoardToken[]) => void;
  setSceneSnapshot: (scenes: RoomScene[], activeScene: RoomScene | null) => void;
  updateScene: (scene: RoomScene) => void;
  activateScene: (scene: RoomScene) => void;
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
  scenes: [],
  activeScene: null,
  roomId: "demo-room",
  self: null,
  setConnectionStatus: (connectionStatus) => set({ connectionStatus }),
  setRoomSnapshot: (roomId, self, members) => set({ roomId, self, members, errorMessage: null }),
  setBoardSnapshot: (tokens) => set({ tokens }),
  setSceneSnapshot: (scenes, activeScene) => set({ scenes, activeScene }),
  updateScene: (scene) => set((state) => ({
    scenes: [...state.scenes.filter((current) => current.scene_id !== scene.scene_id), scene],
    activeScene: scene.is_active ? scene : state.activeScene,
  })),
  activateScene: (scene) => set((state) => ({
    scenes: state.scenes.map((current) => ({ ...current, is_active: current.scene_id === scene.scene_id })),
    activeScene: scene,
  })),
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
