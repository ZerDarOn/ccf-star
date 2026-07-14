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
  token_id?: string | null;
  face_id?: string | null;
  character_name?: string;
  character_color?: string;
  tab_id?: string | null;
  show_dialogue?: boolean;
}

export interface ChatTab {
  tab_id: string;
  room_id: string;
  name: string;
  tab_type: "main" | "info" | "chat" | "custom";
  show_dialogue: boolean;
  is_default: boolean;
  sort_order: number;
}

export interface BoardToken {
  token_id: string;
  owner_user_id: string;
  name: string;
  x: number;
  y: number;
  color: string;
  presentation?: TokenPresentation;
  faces?: TokenFace[];
}

export interface TokenPresentation {
  token_id: string;
  token_type: "npc" | "character";
  image_url: string | null;
  scale: number;
  active_face_id: string | null;
}

export interface TokenFace {
  face_id: string;
  token_id: string;
  label: string;
  image_url: string;
  trigger?: string;
}

export interface RoomScene {
  scene_id: string;
  name: string;
  background_url: string;
  is_active: boolean;
}

export interface SceneLayer {
  layer_id: string;
  scene_id: string;
  layer_type: "background" | "foreground" | "panel" | "marker";
  name: string;
  image_url: string | null;
  text: string;
  x: number;
  y: number;
  width: number;
  height: number;
  z_index: number;
  visible: boolean;
}

export type BgmSlot = "bgm01" | "bgm02";

export interface BgmTrack {
  bgm_id: string;
  room_id: string;
  slot: BgmSlot;
  name: string;
  audio_url: string;
  loop: boolean;
}

export interface BgmPlayback {
  slot: BgmSlot;
  action: "play" | "pause" | "stop";
  is_playing: boolean;
  position: number;
}

interface RoomState {
  connectionStatus: ConnectionStatus;
  errorMessage: string | null;
  members: RoomMember[];
  messages: ChatMessage[];
  chatTabs: ChatTab[];
  tokens: BoardToken[];
  scenes: RoomScene[];
  activeScene: RoomScene | null;
  sceneLayers: SceneLayer[];
  bgmTracks: BgmTrack[];
  bgmPlayback: BgmPlayback[];
  roomId: string;
  self: RoomMember | null;
  setConnectionStatus: (connectionStatus: ConnectionStatus) => void;
  setRoomSnapshot: (roomId: string, self: RoomMember, members: RoomMember[]) => void;
  setBoardSnapshot: (tokens: BoardToken[]) => void;
  setChatTabs: (tabs: ChatTab[]) => void;
  upsertChatTab: (tab: ChatTab) => void;
  setSceneSnapshot: (scenes: RoomScene[], activeScene: RoomScene | null) => void;
  setSceneLayers: (layers: SceneLayer[]) => void;
  upsertSceneLayer: (layer: SceneLayer) => void;
  removeSceneLayer: (layerId: string) => void;
  setBgmSnapshot: (tracks: BgmTrack[], playback: BgmPlayback[]) => void;
  upsertBgmTrack: (track: BgmTrack) => void;
  removeBgmTrack: (bgmId: string) => void;
  setBgmPlayback: (playback: BgmPlayback) => void;
  updateScene: (scene: RoomScene) => void;
  activateScene: (scene: RoomScene) => void;
  addMember: (member: RoomMember) => void;
  updateMember: (member: RoomMember) => void;
  removeMember: (userId: string) => void;
  addMessage: (message: ChatMessage) => void;
  upsertToken: (token: BoardToken) => void;
  updateTokenPresentation: (presentation: TokenPresentation) => void;
  upsertTokenFace: (face: TokenFace) => void;
  removeTokenFace: (tokenId: string, faceId: string) => void;
  removeToken: (tokenId: string) => void;
  setErrorMessage: (errorMessage: string | null) => void;
}

export const useRoomStore = create<RoomState>((set) => ({
  connectionStatus: "disconnected",
  errorMessage: null,
  members: [],
  messages: [],
  chatTabs: [],
  tokens: [],
  scenes: [],
  activeScene: null,
  sceneLayers: [],
  bgmTracks: [],
  bgmPlayback: [],
  roomId: "demo-room",
  self: null,
  setConnectionStatus: (connectionStatus) => set({ connectionStatus }),
  setRoomSnapshot: (roomId, self, members) => set({ roomId, self, members, errorMessage: null }),
  setBoardSnapshot: (tokens) => set({ tokens }),
  setChatTabs: (chatTabs) => set({ chatTabs }),
  upsertChatTab: (tab) => set((state) => ({ chatTabs: [...state.chatTabs.filter((current) => current.tab_id !== tab.tab_id), tab].sort((a, b) => a.sort_order - b.sort_order) })),
  setSceneSnapshot: (scenes, activeScene) => set({ scenes, activeScene }),
  setSceneLayers: (sceneLayers) => set({ sceneLayers }),
  upsertSceneLayer: (layer) => set((state) => ({ sceneLayers: [...state.sceneLayers.filter((current) => current.layer_id !== layer.layer_id), layer] })),
  removeSceneLayer: (layerId) => set((state) => ({ sceneLayers: state.sceneLayers.filter((layer) => layer.layer_id !== layerId) })),
  setBgmSnapshot: (bgmTracks, bgmPlayback) => set({ bgmTracks, bgmPlayback }),
  upsertBgmTrack: (track) => set((state) => ({ bgmTracks: [...state.bgmTracks.filter((current) => current.slot !== track.slot && current.bgm_id !== track.bgm_id), track] })),
  removeBgmTrack: (bgmId) => set((state) => ({ bgmTracks: state.bgmTracks.filter((track) => track.bgm_id !== bgmId) })),
  setBgmPlayback: (playback) => set((state) => ({ bgmPlayback: [...state.bgmPlayback.filter((current) => current.slot !== playback.slot), playback] })),
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
  updateTokenPresentation: (presentation) => set((state) => ({
    tokens: state.tokens.map((token) => token.token_id === presentation.token_id ? { ...token, presentation, faces: token.faces ?? [] } : token),
  })),
  upsertTokenFace: (face) => set((state) => ({
    tokens: state.tokens.map((token) => token.token_id !== face.token_id ? token : { ...token, faces: [...(token.faces ?? []).filter((current) => current.face_id !== face.face_id), face] }),
  })),
  removeTokenFace: (tokenId, faceId) => set((state) => ({
    tokens: state.tokens.map((token) => token.token_id !== tokenId ? token : { ...token, faces: (token.faces ?? []).filter((face) => face.face_id !== faceId) }),
  })),
  removeToken: (tokenId) => set((state) => ({ tokens: state.tokens.filter((token) => token.token_id !== tokenId) })),
  setErrorMessage: (errorMessage) => set({ errorMessage }),
}));
