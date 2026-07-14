import { useEffect, useRef, useState } from "react";
import type { DragEvent, FormEvent, PointerEvent as ReactPointerEvent } from "react";
import { AccountUser, useAuthStore } from "./authStore";
import { BgmPlayback, BgmSlot, BgmTrack, BoardToken, ChatMessage, ChatTab, RoomMember, RoomScene, SceneLayer, TokenFace, TokenPresentation, useRoomStore } from "./roomStore";
import { AuthPage } from "./AuthPage";
import { HomePage, RoomSummary } from "./HomePage";
import { RoomDrawer } from "./RoomDrawer";
import { RoomAiPanel, type AiLogSummary, type AiProviderSummary, type KnowledgeBaseSummary, type KnowledgeDocumentSummary, type RoomAiConfig } from "./RoomAiPanel";
import { KnowledgeBasePanel } from "./KnowledgeBasePanel";
import { RoomKnowledgePanel } from "./RoomKnowledgePanel";
import { CharacterLibraryPanel, type CharacterSummary } from "./CharacterLibraryPanel";
import { RoomCharacterPanel, type RoomCharacterSummary } from "./RoomCharacterPanel";
import { DiceConfigPanel, type DiceShortcut } from "./DiceConfigPanel";

type RoomEvent =
  | { type: "room.connected"; room_id: string; self: RoomMember; members: RoomMember[]; board: { tokens: BoardToken[] }; scenes: RoomScene[]; active_scene: RoomScene | null; scene_layers: SceneLayer[]; bgm_tracks: BgmTrack[]; bgm_playback: BgmPlayback[]; chat_tabs: ChatTab[] }
  | { type: "member.joined"; member: RoomMember }
  | { type: "member.left"; user_id: string }
  | { type: "member.role.updated"; member: RoomMember }
  | { type: "member.name.updated"; member: RoomMember }
  | { type: "member.removed"; user_id: string }
  | { type: "chat.message"; message: ChatMessage }
  | { type: "dice.result"; result: DiceResult }
  | { type: "scene.updated"; scene: RoomScene }
  | { type: "scene.activated"; scene: RoomScene; layers: SceneLayer[] }
  | { type: "scene.layer.upserted"; layer: SceneLayer }
  | { type: "scene.layer.removed"; scene_id: string; layer_id: string }
  | { type: "bgm.track.upserted"; track: BgmTrack }
  | { type: "bgm.track.removed"; bgm_id: string }
  | { type: "bgm.control"; playback: BgmPlayback }
  | { type: "chat.tab.created"; tab: ChatTab }
  | { type: "board.token.upserted"; token: BoardToken }
  | { type: "board.token.removed"; token_id: string }
  | { type: "board.token.presentation.updated"; presentation: TokenPresentation }
  | { type: "board.token.face.upserted"; face: TokenFace }
  | { type: "board.token.face.removed"; token_id: string; face_id: string }
  | { type: "error"; code: string };

const browserOrigin = typeof window === "undefined" ? "http://127.0.0.1:5173" : window.location.origin;
const websocketOrigin = browserOrigin.replace(/^http/, "ws");
const websocketBaseUrl = import.meta.env.VITE_API_WS_URL ?? websocketOrigin;
const apiBaseUrl = import.meta.env.VITE_API_URL ?? browserOrigin;

interface RoomAccessResponse {
  room_id: string;
  access_token: string;
}

interface AuthResponse {
  user: AccountUser;
  access_token: string;
  refresh_token: string;
}

interface DiceResult {
  roll_id: string;
  user_id: string;
  display_name: string;
  expression: string;
  rolls: number[];
  modifier: number;
  total: number;
  tab_id?: string | null;
}

type AppView = "auth" | "home" | "room";
type RoomDrawerName = "ai" | "audio" | "characters" | "dice" | "knowledge" | "members" | "none" | "scene";

const defaultDiceShortcuts: DiceShortcut[] = [
  { id: "d100", label: "百分骰", expression: "1d100" },
  { id: "d20", label: "D20", expression: "1d20" },
  { id: "d6", label: "D6", expression: "1d6" },
  { id: "damage", label: "伤害", expression: "2d6+3" },
];

export function App() {
  const socketRef = useRef<WebSocket | null>(null);
  const boardRef = useRef<HTMLDivElement | null>(null);
  const sceneLayerPointerRef = useRef<{ layer: SceneLayer; mode: "move" | "resize"; startX: number; startY: number } | null>(null);
  const audioRefs = useRef<Record<BgmSlot, HTMLAudioElement | null>>({ bgm01: null, bgm02: null });
  const [roomInput, setRoomInput] = useState("demo-room");
  const [nameInput, setNameInput] = useState("苏鸣澈");
  const [messageInput, setMessageInput] = useState("");
  const [chatTabId, setChatTabId] = useState<string | null>(null);
  const [chatNameInput, setChatNameInput] = useState("");
  const [memberNameInput, setMemberNameInput] = useState("");
  const [diceShortcuts, setDiceShortcuts] = useState<DiceShortcut[]>(defaultDiceShortcuts);
  const [chatColorInput, setChatColorInput] = useState("#d7b56d");
  const [chatTokenId, setChatTokenId] = useState<string | null>(null);
  const [chatFaceId, setChatFaceId] = useState<string | null>(null);
  const [chatCollapsed, setChatCollapsed] = useState(false);
  const [showChannelForm, setShowChannelForm] = useState(false);
  const [channelNameInput, setChannelNameInput] = useState("");
  const [channelDialogueInput, setChannelDialogueInput] = useState(false);
  const [sceneNameInput, setSceneNameInput] = useState("");
  const [sceneBackgroundInput, setSceneBackgroundInput] = useState("");
  const [selectedTokenId, setSelectedTokenId] = useState<string | null>(null);
  const [tokenNameInput, setTokenNameInput] = useState("");
  const [tokenScaleInput, setTokenScaleInput] = useState("1");
  const [tokenImageFile, setTokenImageFile] = useState<File | null>(null);
  const [faceLabelInput, setFaceLabelInput] = useState("");
  const [faceTriggerInput, setFaceTriggerInput] = useState("");
  const [faceImageFile, setFaceImageFile] = useState<File | null>(null);
  const [layerTypeInput, setLayerTypeInput] = useState<SceneLayer["layer_type"]>("panel");
  const [layerNameInput, setLayerNameInput] = useState("");
  const [layerTextInput, setLayerTextInput] = useState("");
  const [layerImageFile, setLayerImageFile] = useState<File | null>(null);
  const [layerShapeInput, setLayerShapeInput] = useState<SceneLayer["shape"]>("rectangle");
  const [layerFitInput, setLayerFitInput] = useState<SceneLayer["image_fit"]>("cover");
  const [layerBlurInput, setLayerBlurInput] = useState("0");
  const [layerOpacityInput, setLayerOpacityInput] = useState("1");
  const [selectedLayerId, setSelectedLayerId] = useState<string | null>(null);
  const [bgmSlotInput, setBgmSlotInput] = useState<BgmSlot>("bgm01");
  const [bgmNameInput, setBgmNameInput] = useState("");
  const [bgmFile, setBgmFile] = useState<File | null>(null);
  const [bgmUploadStatus, setBgmUploadStatus] = useState("");
  const [bgmVolume, setBgmVolume] = useState<Record<BgmSlot, number>>({ bgm01: 0.8, bgm02: 0.8 });
  const [bgmMuted, setBgmMuted] = useState<Record<BgmSlot, boolean>>({ bgm01: false, bgm02: false });
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [usernameInput, setUsernameInput] = useState("");
  const [passwordInput, setPasswordInput] = useState("");
  const { accessToken, refreshToken, user, setSession, clearSession } = useAuthStore();
  const { connectionStatus, errorMessage, members, messages, chatTabs, self, roomId, tokens, scenes, activeScene, sceneLayers, bgmTracks, bgmPlayback, setConnectionStatus, setRoomSnapshot, setBoardSnapshot, setChatTabs, upsertChatTab, setSceneSnapshot, setSceneLayers, upsertSceneLayer, removeSceneLayer, updateScene, activateScene, addMember, updateMember, removeMember, addMessage, upsertToken, removeToken, updateTokenPresentation, upsertTokenFace, removeTokenFace, setBgmSnapshot, upsertBgmTrack, removeBgmTrack, setBgmPlayback, setErrorMessage } = useRoomStore();
  const [appView, setAppView] = useState<AppView>(() => user ? "home" : "auth");
  const [activeDrawer, setActiveDrawer] = useState<RoomDrawerName>("none");
  const [rooms, setRooms] = useState<RoomSummary[]>([]);
  const [isLoadingRooms, setIsLoadingRooms] = useState(false);
  const [aiConfig, setAiConfig] = useState<RoomAiConfig>({ room_id: null, provider_id: null, enabled: false, assistant_name: "星语", system_prompt: "你是一个温和、有人情味的跑团助手。", avatar_url: null, trigger_mode: "mention", scene_context_enabled: true, knowledge_base_ids: [] });
  const [aiProviders, setAiProviders] = useState<AiProviderSummary[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseSummary[]>([]);
  const [knowledgeDocuments, setKnowledgeDocuments] = useState<KnowledgeDocumentSummary[]>([]);
  const [selectedKnowledgeBaseId, setSelectedKnowledgeBaseId] = useState("");
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [documentTitleInput, setDocumentTitleInput] = useState("");
  const [documentContentInput, setDocumentContentInput] = useState("");
  const [documentCategoryInput, setDocumentCategoryInput] = useState("");
  const [documentAiEnabledInput, setDocumentAiEnabledInput] = useState(true);
  const [aiLogs, setAiLogs] = useState<AiLogSummary[]>([]);
  const [providerNameInput, setProviderNameInput] = useState("");
  const [providerBaseUrlInput, setProviderBaseUrlInput] = useState("");
  const [providerModelInput, setProviderModelInput] = useState("");
  const [providerApiKeyInput, setProviderApiKeyInput] = useState("");
  const [knowledgeNameInput, setKnowledgeNameInput] = useState("");
  const [knowledgeKindInput, setKnowledgeKindInput] = useState<"knowledge" | "documents">("knowledge");
  const [knowledgeParentIdInput, setKnowledgeParentIdInput] = useState("");
  const [roomMountedKnowledgeIds, setRoomMountedKnowledgeIds] = useState<string[]>([]);
  const [tokenShapeInput, setTokenShapeInput] = useState<BoardToken["shape"]>("circle");
  const [tokenCharacterIdInput, setTokenCharacterIdInput] = useState<string | null>(null);
  const [homeKnowledgeOpen, setHomeKnowledgeOpen] = useState(false);
  const [homeKnowledgeKind, setHomeKnowledgeKind] = useState<"knowledge" | "documents">("knowledge");
  const [homeCharactersOpen, setHomeCharactersOpen] = useState(false);
  const [characters, setCharacters] = useState<CharacterSummary[]>([]);
  const [selectedCharacterId, setSelectedCharacterId] = useState<string | null>(null);
  const [characterNameInput, setCharacterNameInput] = useState("");
  const [characterStInput, setCharacterStInput] = useState("");
  const [roomCharacters, setRoomCharacters] = useState<RoomCharacterSummary[]>([]);

  useEffect(() => () => socketRef.current?.close(), []);

  useEffect(() => {
    const saved = window.localStorage.getItem("coc-star:dice-shortcuts");
    if (!saved) return;
    try {
      const parsed = JSON.parse(saved) as DiceShortcut[];
      if (Array.isArray(parsed) && parsed.every((item) => typeof item.id === "string" && typeof item.label === "string" && typeof item.expression === "string")) setDiceShortcuts(parsed);
    } catch {
      window.localStorage.removeItem("coc-star:dice-shortcuts");
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem("coc-star:dice-shortcuts", JSON.stringify(diceShortcuts));
  }, [diceShortcuts]);

  useEffect(() => {
    if (!user) setAppView("auth");
  }, [user]);

  const loadMyRooms = async () => {
    if (!accessToken || !user) return;
    setIsLoadingRooms(true);
    try {
      const response = await fetch(`${apiBaseUrl}/api/rooms`, { headers: { Authorization: `Bearer ${accessToken}` } });
      if (!response.ok) throw new Error("房间列表读取失败");
      const result = await response.json() as { rooms: RoomSummary[] };
      setRooms(result.rooms);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "房间列表读取失败");
    } finally {
      setIsLoadingRooms(false);
    }
  };

  const loadCharacters = async () => {
    if (!accessToken) return;
    const response = await fetch(`${apiBaseUrl}/api/characters`, { headers: { Authorization: `Bearer ${accessToken}` } });
    if (!response.ok) { setErrorMessage("角色库读取失败"); return; }
    const result = await response.json() as { characters: CharacterSummary[] };
    setCharacters(result.characters);
    if (!selectedCharacterId && result.characters[0]) setSelectedCharacterId(result.characters[0].character_id);
  };

  const importStCharacter = async (event: FormEvent) => {
    event.preventDefault();
    if (!accessToken || !characterNameInput.trim() || !characterStInput.trim()) return;
    const response = await fetch(`${apiBaseUrl}/api/characters/import-st`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` }, body: JSON.stringify({ name: characterNameInput, text: characterStInput }) });
    if (!response.ok) { setErrorMessage(".st 角色卡导入失败"); return; }
    const result = await response.json() as { character: CharacterSummary };
    setCharacterNameInput(""); setCharacterStInput(""); setSelectedCharacterId(result.character.character_id); setErrorMessage(null); await loadCharacters();
  };

  const deleteCharacter = async (characterId: string) => {
    if (!accessToken || !window.confirm("确定删除这张角色卡吗？")) return;
    const response = await fetch(`${apiBaseUrl}/api/characters/${encodeURIComponent(characterId)}`, { method: "DELETE", headers: { Authorization: `Bearer ${accessToken}` } });
    if (!response.ok) { setErrorMessage("角色卡删除失败"); return; }
    setSelectedCharacterId(null); await loadCharacters();
  };

  const loadRoomCharacters = async () => {
    if (!accessToken || !roomId) return;
    const [libraryResponse, roomResponse] = await Promise.all([
      fetch(`${apiBaseUrl}/api/characters`, { headers: { Authorization: `Bearer ${accessToken}` } }),
      fetch(`${apiBaseUrl}/api/rooms/${encodeURIComponent(roomId)}/characters`, { headers: { Authorization: `Bearer ${accessToken}` } }),
    ]);
    if (!libraryResponse.ok || !roomResponse.ok) { setErrorMessage("房间角色读取失败"); return; }
    const libraryResult = await libraryResponse.json() as { characters: CharacterSummary[] };
    const roomResult = await roomResponse.json() as { characters: RoomCharacterSummary[] };
    setCharacters(libraryResult.characters); setRoomCharacters(roomResult.characters);
  };

  const loadCharacterIntoRoom = async (characterId: string) => {
    if (!accessToken || !roomId) return;
    const response = await fetch(`${apiBaseUrl}/api/rooms/${encodeURIComponent(roomId)}/characters/${encodeURIComponent(characterId)}`, { method: "POST", headers: { Authorization: `Bearer ${accessToken}` } });
    if (!response.ok) { setErrorMessage("角色加载失败"); return; }
    setErrorMessage(null); await loadRoomCharacters();
  };

  const handleRemoveRoom = async (room: RoomSummary) => {
    const action = room.is_owner ? "删除这个房间及其场景、素材和聊天记录" : "退出这个房间";
    if (!window.confirm(`确定要${action}吗？`)) return;
    if (!accessToken) return;
    try {
      const response = await fetch(`${apiBaseUrl}/api/rooms/${encodeURIComponent(room.room_id)}`, { method: "DELETE", headers: { Authorization: `Bearer ${accessToken}` } });
      if (!response.ok) throw new Error(room.is_owner ? "房间删除失败" : "退出房间失败");
      setRooms((current) => current.filter((item) => item.room_id !== room.room_id));
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "房间操作失败");
    }
  };

  useEffect(() => {
    if (appView === "home" && user) void loadMyRooms();
  }, [appView, user, accessToken]);

  useEffect(() => () => {
    (Object.keys(audioRefs.current) as BgmSlot[]).forEach((slot) => {
      audioRefs.current[slot]?.pause();
      audioRefs.current[slot] = null;
    });
  }, []);

  useEffect(() => {
    bgmPlayback.forEach((playback) => {
      const track = bgmTracks.find((item) => item.slot === playback.slot);
      if (!track) return;
      const currentAudio = audioRefs.current[playback.slot];
      const audioUrl = new URL(track.audio_url, window.location.origin).href;
      const audio = currentAudio ?? new Audio(audioUrl);
      if (!currentAudio || currentAudio.src !== audioUrl) {
        currentAudio?.pause();
        audio.src = audioUrl;
        audioRefs.current[playback.slot] = audio;
      }
      audio.loop = track.loop;
      audio.volume = bgmVolume[playback.slot];
      audio.muted = bgmMuted[playback.slot];
      if (playback.action === "stop") {
        audio.pause();
        audio.currentTime = 0;
      } else if (playback.action === "pause") {
        audio.pause();
        audio.currentTime = playback.position;
      } else {
        audio.currentTime = playback.position;
        void audio.play().catch(() => setErrorMessage("浏览器阻止了自动播放，请点击播放按钮"));
      }
    });
  }, [bgmPlayback, bgmTracks, setErrorMessage]);

  useEffect(() => {
    (Object.keys(audioRefs.current) as BgmSlot[]).forEach((slot) => {
      const audio = audioRefs.current[slot];
      if (!audio) return;
      audio.volume = bgmVolume[slot];
      audio.muted = bgmMuted[slot];
    });
  }, [bgmMuted, bgmVolume]);

  useEffect(() => {
    const selectedToken = tokens.find((token) => token.token_id === selectedTokenId);
    if (!selectedToken) return;
    setTokenNameInput(selectedToken.name);
    setTokenScaleInput(String(selectedToken.presentation?.scale ?? 1));
    setTokenShapeInput(selectedToken.shape);
    setTokenCharacterIdInput(selectedToken.character_id ?? null);
  }, [selectedTokenId]);

  useEffect(() => {
    if (self && !chatNameInput) setChatNameInput(self.display_name);
    if (!chatTabId && chatTabs.length > 0) setChatTabId(chatTabs.find((tab) => tab.tab_type === "main")?.tab_id ?? chatTabs[0].tab_id);
  }, [self, chatTabs, chatNameInput, chatTabId]);

  useEffect(() => {
    const token = tokens.find((item) => item.token_id === chatTokenId);
    setChatFaceId(token?.presentation?.active_face_id ?? null);
  }, [chatTokenId, tokens]);

  const handleAuthSubmit = async (event: FormEvent) => {
    event.preventDefault();
    try {
      const response = await fetch(`${apiBaseUrl}/api/auth/${authMode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: usernameInput.trim(), password: passwordInput }),
      });
      if (!response.ok) throw new Error(authMode === "login" ? "登录失败，请检查账号和密码" : "注册失败，账号可能已存在");
      const result = await response.json() as AuthResponse;
      setSession(result.user, result.access_token, result.refresh_token);
      setNameInput(result.user.username);
      setPasswordInput("");
      setErrorMessage(null);
      setAppView("home");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "账号操作失败");
    }
  };

  const handleLogout = () => {
    socketRef.current?.close();
    clearSession();
    setConnectionStatus("disconnected");
    setActiveDrawer("none");
    setRooms([]);
    setAppView("auth");
  };

  const handleLeaveRoom = () => {
    socketRef.current?.close();
    setActiveDrawer("none");
    setConnectionStatus("disconnected");
    setAppView("home");
  };

  const requestRoomEndpoint = async (url: string, body: object) => {
    if (!accessToken || !refreshToken || !user) throw new Error("请先登录账号");
    let currentAccessToken = accessToken;
    let response = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${currentAccessToken}` }, body: JSON.stringify(body) });
    if (response.status !== 401) return response;
    const refreshResponse = await fetch(`${apiBaseUrl}/api/auth/refresh`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: refreshToken }) });
    if (!refreshResponse.ok) { clearSession(); throw new Error("登录已过期，请重新登录"); }
    const refreshed = await refreshResponse.json() as Pick<AuthResponse, "access_token" | "refresh_token">;
    currentAccessToken = refreshed.access_token;
    setSession(user, refreshed.access_token, refreshed.refresh_token);
    response = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${currentAccessToken}` }, body: JSON.stringify(body) });
    return response;
  };

  const joinRoom = async (roomIdToJoin: string) => {
    const nextRoomId = roomIdToJoin.trim();
    const nextName = nameInput.trim();
    if (!nextRoomId || !nextName) {
      setErrorMessage("房间号和玩家名不能为空");
      return;
    }

    setErrorMessage(null);
    setConnectionStatus("connecting");
    try {
      const response = await requestRoomEndpoint(`${apiBaseUrl}/api/rooms/${encodeURIComponent(nextRoomId)}/join`, { display_name: nextName });
      if (!response.ok) throw new Error(response.status === 404 ? "找不到这个房间" : "加入房间失败");
      const access = await response.json() as RoomAccessResponse;
      connectToRoom(access.room_id, access.access_token);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "加入房间失败");
      setConnectionStatus("error");
    }
  };

  const handleJoinRoom = (event: FormEvent) => {
    event.preventDefault();
    void joinRoom(roomInput);
  };

  const handleCreateRoom = async () => {
    const nextName = nameInput.trim();
    if (!nextName) {
      setErrorMessage("玩家名不能为空");
      return;
    }
    setErrorMessage(null);
    setConnectionStatus("connecting");
    try {
      const response = await requestRoomEndpoint(`${apiBaseUrl}/api/rooms`, { display_name: nextName });
      if (!response.ok) throw new Error("创建房间失败");
      const access = await response.json() as RoomAccessResponse;
      setRoomInput(access.room_id);
      connectToRoom(access.room_id, access.access_token);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "创建房间失败");
      setConnectionStatus("error");
    }
  };

  const handleOpenRoom = (nextRoomId: string) => {
    setRoomInput(nextRoomId);
    void joinRoom(nextRoomId);
  };

  const connectToRoom = (nextRoomId: string, accessToken: string) => {
    socketRef.current?.close();
    const socket = new WebSocket(`${websocketBaseUrl}/ws/rooms/${encodeURIComponent(nextRoomId)}`);
    socketRef.current = socket;
    socket.onopen = () => socket.send(JSON.stringify({ type: "auth", access_token: accessToken }));
    socket.onmessage = (event) => handleRoomEvent(event.data);
    socket.onerror = () => {
      setErrorMessage("无法连接到房间服务，请确认 API 已启动");
      setConnectionStatus("error");
    };
    socket.onclose = () => setConnectionStatus("disconnected");
  };

  const loadAiWorkspace = async () => {
    if (!accessToken || !roomId) return;
    const headers = { Authorization: `Bearer ${accessToken}` };
    try {
      const documentsPromise = selectedKnowledgeBaseId ? fetch(`${apiBaseUrl}/api/knowledge-bases/${encodeURIComponent(selectedKnowledgeBaseId)}/documents`, { headers }) : Promise.resolve(null);
      const [providerResponse, knowledgeResponse, configResponse, logsResponse, documentsResponse, roomKnowledgeResponse] = await Promise.all([fetch(`${apiBaseUrl}/api/ai/providers`, { headers }), fetch(`${apiBaseUrl}/api/knowledge-bases`, { headers }), fetch(`${apiBaseUrl}/api/rooms/${encodeURIComponent(roomId)}/ai`, { headers }), fetch(`${apiBaseUrl}/api/rooms/${encodeURIComponent(roomId)}/ai/logs`, { headers }), documentsPromise, fetch(`${apiBaseUrl}/api/rooms/${encodeURIComponent(roomId)}/knowledge`, { headers })]);
      if (documentsResponse && !documentsResponse.ok) throw new Error("文档读取失败");
      if (!providerResponse.ok || !knowledgeResponse.ok || !configResponse.ok || !logsResponse.ok || !roomKnowledgeResponse.ok) throw new Error("AI 配置读取失败");
      const providerResult = await providerResponse.json() as { providers: AiProviderSummary[] };
      const knowledgeResult = await knowledgeResponse.json() as { knowledge_bases: KnowledgeBaseSummary[] };
      const configResult = await configResponse.json() as { config: RoomAiConfig };
      const logsResult = await logsResponse.json() as { logs: AiLogSummary[] };
      const roomKnowledgeResult = await roomKnowledgeResponse.json() as { knowledge_base_ids: string[] };
      const documentsResult = documentsResponse ? await documentsResponse.json() as { documents: KnowledgeDocumentSummary[] } : { documents: [] };
      setAiProviders(providerResult.providers); setKnowledgeBases(knowledgeResult.knowledge_bases); setAiConfig(configResult.config); setAiLogs(logsResult.logs); setKnowledgeDocuments(documentsResult.documents); setRoomMountedKnowledgeIds(roomKnowledgeResult.knowledge_base_ids);
    } catch (error) { setErrorMessage(error instanceof Error ? error.message : "AI 配置读取失败"); }
  };

  const loadKnowledgeWorkspace = async () => {
    if (!accessToken) return;
    const headers = { Authorization: `Bearer ${accessToken}` };
    try {
      const basesResponse = await fetch(`${apiBaseUrl}/api/knowledge-bases`, { headers });
      if (!basesResponse.ok) throw new Error("知识库读取失败");
      const result = await basesResponse.json() as { knowledge_bases: KnowledgeBaseSummary[] };
      setKnowledgeBases(result.knowledge_bases);
      if (selectedKnowledgeBaseId) {
        const documentsResponse = await fetch(`${apiBaseUrl}/api/knowledge-bases/${encodeURIComponent(selectedKnowledgeBaseId)}/documents`, { headers });
        if (!documentsResponse.ok) throw new Error("文档读取失败");
        const documentsResult = await documentsResponse.json() as { documents: KnowledgeDocumentSummary[] };
        setKnowledgeDocuments(documentsResult.documents);
      }
    } catch (error) { setErrorMessage(error instanceof Error ? error.message : "知识库读取失败"); }
  };

  const saveAiProvider = async (event: FormEvent) => {
    event.preventDefault();
    if (!accessToken) return;
    const response = await fetch(`${apiBaseUrl}/api/ai/providers`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` }, body: JSON.stringify({ name: providerNameInput, base_url: providerBaseUrlInput, model: providerModelInput, api_key: providerApiKeyInput }) });
    if (!response.ok) { setErrorMessage("厂商配置保存失败"); return; }
    setProviderApiKeyInput(""); setProviderNameInput(""); await loadAiWorkspace();
  };

  const saveRoomAiConfig = async (event: FormEvent) => {
    event.preventDefault();
    if (!accessToken) return;
    const response = await fetch(`${apiBaseUrl}/api/rooms/${encodeURIComponent(roomId)}/ai`, { method: "PUT", headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` }, body: JSON.stringify(aiConfig) });
    if (!response.ok) { setErrorMessage("房间 AI 配置保存失败"); return; }
    setErrorMessage(null); await loadAiWorkspace();
  };

  const saveRoomKnowledge = async () => {
    if (!accessToken) return;
    const response = await fetch(`${apiBaseUrl}/api/rooms/${encodeURIComponent(roomId)}/knowledge`, { method: "PUT", headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` }, body: JSON.stringify({ knowledge_base_ids: roomMountedKnowledgeIds }) });
    if (!response.ok) { setErrorMessage("房间知识库挂载保存失败"); return; }
    setErrorMessage(null);
  };

  const createKnowledgeBase = async (event: FormEvent) => {
    event.preventDefault();
    if (!accessToken || !knowledgeNameInput.trim()) return;
    const response = await fetch(`${apiBaseUrl}/api/knowledge-bases`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` }, body: JSON.stringify({ name: knowledgeNameInput, kind: knowledgeKindInput, parent_id: knowledgeParentIdInput || null }) });
    if (!response.ok) { setErrorMessage("知识库创建失败"); return; }
    setKnowledgeNameInput(""); setKnowledgeParentIdInput(""); await (homeKnowledgeOpen ? loadKnowledgeWorkspace() : loadAiWorkspace());
  };

  const handleKnowledgeBaseChange = (value: string) => {
    setSelectedKnowledgeBaseId(value); setSelectedDocumentId(null); setDocumentTitleInput(""); setDocumentCategoryInput(""); setDocumentContentInput(""); setDocumentAiEnabledInput(true);
  };

  const saveKnowledgeDocument = async (event: FormEvent) => {
    event.preventDefault();
    if (!accessToken || !selectedKnowledgeBaseId) return;
    const response = await fetch(`${apiBaseUrl}/api/knowledge-bases/${encodeURIComponent(selectedKnowledgeBaseId)}/documents`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` }, body: JSON.stringify({ document_id: selectedDocumentId, title: documentTitleInput, category: documentCategoryInput || "未分类", content: documentContentInput, ai_enabled: documentAiEnabledInput }) });
    if (!response.ok) { setErrorMessage("文档保存失败"); return; }
    setSelectedDocumentId(null); setDocumentTitleInput(""); setDocumentCategoryInput(""); setDocumentContentInput(""); setDocumentAiEnabledInput(true); await (homeKnowledgeOpen ? loadKnowledgeWorkspace() : loadAiWorkspace());
  };

  const importKnowledgeFile = async (file: File) => {
    if (!accessToken || !selectedKnowledgeBaseId) return;
    const response = await fetch(`${apiBaseUrl}/api/knowledge-bases/${encodeURIComponent(selectedKnowledgeBaseId)}/files`, { method: "POST", headers: { Authorization: `Bearer ${accessToken}`, "Content-Type": file.type || "text/plain", "X-File-Name": file.name }, body: file });
    if (!response.ok) { setErrorMessage("文件导入失败，请确认格式和大小"); return; }
    setErrorMessage(null); await loadKnowledgeWorkspace();
  };

  const deleteKnowledgeDocument = async (documentId: string) => {
    if (!accessToken || !selectedKnowledgeBaseId || !window.confirm("确定删除这篇文档吗？")) return;
    const response = await fetch(`${apiBaseUrl}/api/knowledge-bases/${encodeURIComponent(selectedKnowledgeBaseId)}/documents/${encodeURIComponent(documentId)}`, { method: "DELETE", headers: { Authorization: `Bearer ${accessToken}` } });
    if (!response.ok) { setErrorMessage("文档删除失败"); return; }
    if (selectedDocumentId === documentId) { setSelectedDocumentId(null); setDocumentTitleInput(""); setDocumentCategoryInput(""); setDocumentContentInput(""); }
    await (homeKnowledgeOpen ? loadKnowledgeWorkspace() : loadAiWorkspace());
  };

  const deleteKnowledgeBase = async (baseId: string) => {
    if (!accessToken || !window.confirm("删除分类会同时删除其子分类、文档以及房间中的挂载引用，确定继续吗？")) return;
    const response = await fetch(`${apiBaseUrl}/api/knowledge-bases/${encodeURIComponent(baseId)}`, { method: "DELETE", headers: { Authorization: `Bearer ${accessToken}` } });
    if (!response.ok) { setErrorMessage("知识库删除失败"); return; }
    setSelectedKnowledgeBaseId(""); setSelectedDocumentId(null); setKnowledgeDocuments([]); setDocumentTitleInput(""); setDocumentCategoryInput(""); setDocumentContentInput(""); setDocumentAiEnabledInput(true);
    await loadKnowledgeWorkspace();
  };

  const handleOpenKnowledgeBase = (kind: "knowledge" | "documents") => {
    setHomeKnowledgeKind(kind); setHomeKnowledgeOpen(true); setKnowledgeKindInput(kind); setSelectedKnowledgeBaseId(""); setSelectedDocumentId(null); setKnowledgeDocuments([]); setDocumentTitleInput(""); setDocumentCategoryInput(""); setDocumentContentInput(""); void loadKnowledgeWorkspace();
  };

  useEffect(() => {
    if (appView === "room" && (activeDrawer === "ai" || activeDrawer === "knowledge")) void loadAiWorkspace();
  }, [activeDrawer, appView, roomId, accessToken, selectedKnowledgeBaseId]);

  useEffect(() => {
    if (appView === "room" && activeDrawer === "characters") void loadRoomCharacters();
  }, [activeDrawer, appView, roomId, accessToken]);

  useEffect(() => {
    if (appView === "home" && homeKnowledgeOpen) void loadKnowledgeWorkspace();
  }, [appView, homeKnowledgeOpen, accessToken, selectedKnowledgeBaseId]);

  useEffect(() => {
    if (appView === "home" && homeCharactersOpen) void loadCharacters();
  }, [appView, homeCharactersOpen, accessToken]);

  const handleRoomEvent = (rawEvent: string) => {
    try {
      const event = JSON.parse(rawEvent) as RoomEvent;
      if (event.type === "room.connected") { setConnectionStatus("connected"); setRoomSnapshot(event.room_id, event.self, event.members); setBoardSnapshot(event.board.tokens); setChatTabs(event.chat_tabs); setSceneSnapshot(event.scenes, event.active_scene); setSceneLayers(event.scene_layers); setBgmSnapshot(event.bgm_tracks, event.bgm_playback); setChatNameInput(event.self.display_name); setMemberNameInput(event.self.display_name); setChatTabId(event.chat_tabs.find((tab) => tab.tab_type === "main")?.tab_id ?? event.chat_tabs[0]?.tab_id ?? null); setAppView("room"); }
      if (event.type === "member.joined") addMember(event.member);
      if (event.type === "member.left") removeMember(event.user_id);
      if (event.type === "member.role.updated") updateMember(event.member);
      if (event.type === "member.name.updated") { updateMember(event.member); if (event.member.user_id === user?.user_id) { setMemberNameInput(event.member.display_name); setChatNameInput(event.member.display_name); } }
      if (event.type === "member.removed") removeMember(event.user_id);
      if (event.type === "chat.message") addMessage(event.message);
      if (event.type === "dice.result") addMessage({ message_id: event.result.roll_id, user_id: event.result.user_id, display_name: event.result.display_name, text: `🎲 ${event.result.expression} = ${event.result.total}（${event.result.rolls.join(" + ")}${event.result.modifier ? ` ${event.result.modifier > 0 ? "+" : ""}${event.result.modifier}` : ""}）`, tab_id: event.result.tab_id });
      if (event.type === "scene.updated") updateScene(event.scene);
      if (event.type === "scene.activated") { activateScene(event.scene); setSceneLayers(event.layers); }
      if (event.type === "scene.layer.upserted") upsertSceneLayer(event.layer);
      if (event.type === "scene.layer.removed") removeSceneLayer(event.layer_id);
      if (event.type === "bgm.track.upserted") { upsertBgmTrack(event.track); setBgmUploadStatus(`${event.track.name} 已装载到 ${event.track.slot.toUpperCase()}`); }
      if (event.type === "bgm.track.removed") { const removedTrack = bgmTracks.find((track) => track.bgm_id === event.bgm_id); if (removedTrack) { audioRefs.current[removedTrack.slot]?.pause(); audioRefs.current[removedTrack.slot] = null; } removeBgmTrack(event.bgm_id); }
      if (event.type === "bgm.control") setBgmPlayback(event.playback);
      if (event.type === "chat.tab.created") upsertChatTab(event.tab);
      if (event.type === "board.token.upserted") upsertToken(event.token);
      if (event.type === "board.token.removed") removeToken(event.token_id);
      if (event.type === "board.token.presentation.updated") updateTokenPresentation(event.presentation);
      if (event.type === "board.token.face.upserted") upsertTokenFace(event.face);
      if (event.type === "board.token.face.removed") removeTokenFace(event.token_id, event.face_id);
      if (event.type === "error") setErrorMessage(`房间服务错误：${event.code}`);
    } catch {
      setErrorMessage("收到无法识别的房间事件");
    }
  };

  const handleCreateScene = (event: FormEvent) => {
    event.preventDefault();
    if (socketRef.current?.readyState !== WebSocket.OPEN || self?.role !== "gm" || !sceneNameInput.trim()) return;
    socketRef.current.send(JSON.stringify({ type: "scene.create", name: sceneNameInput.trim(), background_url: sceneBackgroundInput.trim() }));
    setSceneNameInput("");
    setSceneBackgroundInput("");
  };

  const handleActivateScene = (sceneId: string) => {
    if (socketRef.current?.readyState !== WebSocket.OPEN || self?.role !== "gm") return;
    socketRef.current.send(JSON.stringify({ type: "scene.activate", scene_id: sceneId }));
  };

  const handleAddLayer = async (event: FormEvent) => {
    event.preventDefault();
    if (!activeScene || self?.role !== "gm" || socketRef.current?.readyState !== WebSocket.OPEN || !layerNameInput.trim()) return;
    if (layerTypeInput !== "marker" && !layerImageFile) {
      setErrorMessage("图片图层需要选择图片");
      return;
    }
    try {
      const imageUrl = layerImageFile ? await uploadAsset(layerImageFile) : null;
      socketRef.current.send(JSON.stringify({ type: "scene.layer.upsert", scene_id: activeScene.scene_id, layer_type: layerTypeInput, name: layerNameInput.trim(), image_url: imageUrl, text: layerTextInput.trim(), x: 0.5, y: 0.5, width: 0.4, height: 0.3, z_index: layerTypeInput === "background" ? -10 : layerTypeInput === "foreground" ? 10 : 0, visible: true, shape: layerShapeInput, image_fit: layerFitInput, blur: Number(layerBlurInput) || 0, opacity: Number(layerOpacityInput) || 1 }));
      setLayerNameInput("");
      setLayerTextInput("");
      setLayerImageFile(null);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "图层上传失败");
    }
  };

  const handleToggleLayer = (layer: SceneLayer) => {
    if (self?.role !== "gm" || socketRef.current?.readyState !== WebSocket.OPEN) return;
    socketRef.current.send(JSON.stringify({ type: "scene.layer.upsert", ...layer, visible: !layer.visible }));
  };

  const handleRemoveLayer = (layer: SceneLayer) => {
    if (self?.role !== "gm" || socketRef.current?.readyState !== WebSocket.OPEN) return;
    socketRef.current.send(JSON.stringify({ type: "scene.layer.remove", scene_id: layer.scene_id, layer_id: layer.layer_id }));
  };

  const handleNudgeLayer = (dx: number, dy: number) => {
    const layer = sceneLayers.find((item) => item.layer_id === selectedLayerId);
    if (!layer || self?.role !== "gm" || socketRef.current?.readyState !== WebSocket.OPEN) return;
    const maxX = Math.max(0, 1 - layer.width);
    const maxY = Math.max(0, 1 - layer.height);
    socketRef.current.send(JSON.stringify({ type: "scene.layer.upsert", ...layer, x: clamp(layer.x + dx, 0, maxX), y: clamp(layer.y + dy, 0, maxY) }));
  };

  const handleLayerPointerDown = (layer: SceneLayer, mode: "move" | "resize", event: ReactPointerEvent<HTMLElement>) => {
    if (self?.role !== "gm" || socketRef.current?.readyState !== WebSocket.OPEN || !boardRef.current) return;
    event.stopPropagation();
    setSelectedLayerId(layer.layer_id);
    sceneLayerPointerRef.current = { layer, mode, startX: event.clientX, startY: event.clientY };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handleLayerPointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const drag = sceneLayerPointerRef.current;
    if (!drag || !boardRef.current) return;
    const bounds = boardRef.current.getBoundingClientRect();
    const dx = (event.clientX - drag.startX) / bounds.width;
    const dy = (event.clientY - drag.startY) / bounds.height;
    const width = drag.mode === "resize" ? clamp(drag.layer.width + dx, 0.05, 1 - drag.layer.x) : drag.layer.width;
    const height = drag.mode === "resize" ? clamp(drag.layer.height + dy, 0.05, 1 - drag.layer.y) : drag.layer.height;
    const x = drag.mode === "move" ? clamp(drag.layer.x + dx, 0, 1 - width) : drag.layer.x;
    const y = drag.mode === "move" ? clamp(drag.layer.y + dy, 0, 1 - height) : drag.layer.y;
    upsertSceneLayer({ ...drag.layer, x, y, width, height });
  };

  const handleLayerPointerUp = () => {
    const drag = sceneLayerPointerRef.current;
    if (!drag) return;
    sceneLayerPointerRef.current = null;
    if (socketRef.current?.readyState !== WebSocket.OPEN) return;
    const layer = sceneLayers.find((item) => item.layer_id === drag.layer.layer_id);
    if (layer) socketRef.current.send(JSON.stringify({ type: "scene.layer.upsert", ...layer }));
  };

  const handleFocusTool = (selector: string) => {
    document.querySelector(selector)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  };

  const handleAddBgm = async (event: FormEvent) => {
    event.preventDefault();
    if (self?.role !== "gm") { setErrorMessage("只有 GM 可以管理声音槽位"); return; }
    if (socketRef.current?.readyState !== WebSocket.OPEN) { setErrorMessage("房间连接尚未就绪"); return; }
    if (!bgmFile) { setErrorMessage("请先选择音频文件"); return; }
    try {
      setBgmUploadStatus("正在上传音频…");
      const audioUrl = await uploadAsset(bgmFile);
      const trackName = bgmNameInput.trim() || bgmFile.name.replace(/\.[^.]+$/, "");
      socketRef.current.send(JSON.stringify({ type: "bgm.track.upsert", slot: bgmSlotInput, name: trackName, audio_url: audioUrl, loop: true }));
      setBgmUploadStatus("音频已上传，正在写入槽位…");
      setBgmNameInput("");
      setBgmFile(null);
    } catch (error) {
      setBgmUploadStatus("");
      setErrorMessage(error instanceof Error ? error.message : "BGM 上传失败");
    }
  };

  const handleBgmControl = (slot: BgmSlot, action: BgmPlayback["action"]) => {
    if (self?.role !== "gm" || socketRef.current?.readyState !== WebSocket.OPEN) return;
    const position = action === "stop" ? 0 : audioRefs.current[slot]?.currentTime ?? 0;
    socketRef.current.send(JSON.stringify({ type: "bgm.control", slot, action, position }));
  };

  const handleBgmVolume = (slot: BgmSlot, volume: number) => {
    setBgmVolume((current) => ({ ...current, [slot]: volume }));
    const audio = audioRefs.current[slot];
    if (audio) audio.volume = volume;
  };

  const handleBgmMute = (slot: BgmSlot) => {
    setBgmMuted((current) => ({ ...current, [slot]: !current[slot] }));
    const audio = audioRefs.current[slot];
    if (audio) audio.muted = !bgmMuted[slot];
  };

  const uploadAsset = async (file: File) => {
    if (!accessToken || !user) throw new Error("请先登录账号");
    const extension = file.name.split(".").pop()?.toLowerCase();
    const inferredTypes: Record<string, string> = { mp3: "audio/mpeg", ogg: "audio/ogg", wav: "audio/wav", m4a: "audio/mp4", aac: "audio/aac", flac: "audio/flac", webm: "audio/webm", png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg", webp: "image/webp", gif: "image/gif" };
    const contentType = file.type || (extension ? inferredTypes[extension] : "");
    if (!contentType) throw new Error("无法识别文件格式");
    const response = await fetch(`${apiBaseUrl}/api/rooms/${encodeURIComponent(roomId)}/assets`, {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}`, "Content-Type": contentType },
      body: file,
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => null) as { detail?: string } | null;
      throw new Error(detail?.detail === "asset_too_large" ? "文件为空或超过大小限制" : detail?.detail === "unsupported_asset_type" ? "暂不支持这种文件格式" : detail?.detail === "asset_upload_disconnected" ? "上传连接中断，请重试；如果使用隧道，请确认隧道仍在线" : "素材上传失败");
    }
    const result = await response.json() as { url: string };
    return result.url;
  };

  const handleSaveToken = async (event: FormEvent) => {
    event.preventDefault();
    const selectedToken = tokens.find((token) => token.token_id === selectedTokenId);
    if (!selectedToken || !self || (self.role !== "gm" && selectedToken.owner_user_id !== self.user_id) || socketRef.current?.readyState !== WebSocket.OPEN) return;
    try {
      const imageUrl = tokenImageFile ? await uploadAsset(tokenImageFile) : selectedToken.presentation?.image_url ?? null;
      socketRef.current.send(JSON.stringify({ type: "board.token.upsert", token_id: selectedToken.token_id, name: tokenNameInput.trim() || selectedToken.name, x: selectedToken.x, y: selectedToken.y, color: selectedToken.color, shape: tokenShapeInput, character_id: tokenCharacterIdInput }));
      socketRef.current.send(JSON.stringify({ type: "board.token.presentation.update", token_id: selectedToken.token_id, token_type: imageUrl ? "character" : "npc", image_url: imageUrl, scale: Number(tokenScaleInput) || 1, active_face_id: selectedToken.presentation?.active_face_id ?? null }));
      setTokenImageFile(null);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Token 保存失败");
    }
  };

  const handleAddFace = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedTokenId || !faceLabelInput.trim() || !faceTriggerInput.trim() || !faceImageFile || socketRef.current?.readyState !== WebSocket.OPEN) return;
    try {
      const imageUrl = await uploadAsset(faceImageFile);
      socketRef.current.send(JSON.stringify({ type: "board.token.face.upsert", token_id: selectedTokenId, label: faceLabelInput.trim(), trigger: faceTriggerInput.trim(), image_url: imageUrl }));
      setFaceLabelInput("");
      setFaceTriggerInput("");
      setFaceImageFile(null);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "差分上传失败");
    }
  };

  const handleRemoveFace = (face: TokenFace) => {
    if (socketRef.current?.readyState !== WebSocket.OPEN) return;
    socketRef.current.send(JSON.stringify({ type: "board.token.face.remove", token_id: face.token_id, face_id: face.face_id }));
  };

  const handleAddToken = () => {
    if (socketRef.current?.readyState !== WebSocket.OPEN) return;
    socketRef.current.send(JSON.stringify({ type: "board.token.upsert", name: nameInput.trim() || "调查员", x: 0.5, y: 0.5, color: "#d7b56d", shape: "circle" }));
  };

  const handleMoveToken = (token: BoardToken, event: DragEvent<HTMLButtonElement>) => {
    if (socketRef.current?.readyState !== WebSocket.OPEN || !boardRef.current) return;
    const bounds = boardRef.current.getBoundingClientRect();
    const x = clamp((event.clientX - bounds.left) / bounds.width, 0, 1);
    const y = clamp((event.clientY - bounds.top) / bounds.height, 0, 1);
    socketRef.current.send(JSON.stringify({ type: "board.token.upsert", ...token, x, y }));
  };

  const handleRemoveToken = (tokenId: string) => {
    if (socketRef.current?.readyState !== WebSocket.OPEN) return;
    socketRef.current.send(JSON.stringify({ type: "board.token.remove", token_id: tokenId }));
  };

  const handleMemberRoleUpdate = (userId: string, role: "gm" | "player") => {
    if (socketRef.current?.readyState !== WebSocket.OPEN) return;
    socketRef.current.send(JSON.stringify({ type: "room.member.role.update", user_id: userId, role }));
  };

  const handleMemberNameUpdate = (event: FormEvent) => {
    event.preventDefault();
    const displayName = memberNameInput.trim();
    if (!displayName || socketRef.current?.readyState !== WebSocket.OPEN) return;
    socketRef.current.send(JSON.stringify({ type: "room.member.name.update", display_name: displayName }));
  };

  const handleMemberRemove = (userId: string) => {
    if (socketRef.current?.readyState !== WebSocket.OPEN) return;
    socketRef.current.send(JSON.stringify({ type: "room.member.remove", user_id: userId }));
  };

  const handleSendMessage = (event: FormEvent) => {
    event.preventDefault();
    const text = messageInput.trim();
    if (!text || socketRef.current?.readyState !== WebSocket.OPEN) return;
    socketRef.current.send(JSON.stringify({ type: "chat.message", text, tab_id: chatTabId, token_id: chatTokenId, character_name: chatNameInput.trim(), character_color: chatColorInput }));
    setMessageInput("");
  };

  const handleChatTokenChange = (tokenId: string | null) => {
    setChatTokenId(tokenId);
  };

  const handleChatFaceChange = (faceId: string) => {
    const token = ownTokens.find((item) => item.token_id === chatTokenId);
    if (!token || socketRef.current?.readyState !== WebSocket.OPEN) return;
    setChatFaceId(faceId || null);
    socketRef.current.send(JSON.stringify({ type: "board.token.presentation.update", token_id: token.token_id, token_type: token.presentation?.image_url ? "character" : "npc", image_url: token.presentation?.image_url ?? null, scale: token.presentation?.scale ?? 1, active_face_id: faceId || null }));
  };

  const handleCreateChatTab = (event: FormEvent) => {
    event.preventDefault();
    if (!channelNameInput.trim() || socketRef.current?.readyState !== WebSocket.OPEN) return;
    socketRef.current.send(JSON.stringify({ type: "chat.tab.create", name: channelNameInput.trim(), show_dialogue: channelDialogueInput }));
    setChannelNameInput("");
    setChannelDialogueInput(false);
    setShowChannelForm(false);
  };

  const visibleMessages = messages.filter((message) => (message.tab_id ?? chatTabs.find((tab) => tab.tab_type === "main")?.tab_id) === chatTabId);

  const selectedToken = tokens.find((token) => token.token_id === selectedTokenId) ?? null;
  const canEditSelectedToken = Boolean(selectedToken && self && (self.role === "gm" || selectedToken.owner_user_id === self.user_id));
  const stageMessage = [...visibleMessages].reverse().find((message) => message.show_dialogue && (message.token_id || message.ai_avatar_url));
  const stageToken = stageMessage ? tokens.find((token) => token.token_id === stageMessage.token_id) : undefined;
  const stageFace = stageToken?.faces?.find((face) => face.face_id === stageMessage?.face_id) ?? stageToken?.faces?.find((face) => face.face_id === stageToken.presentation?.active_face_id);
  const stageImage = stageFace?.image_url ?? stageToken?.presentation?.image_url ?? stageMessage?.ai_avatar_url;
  const ownTokens = tokens.filter((token) => token.owner_user_id === self?.user_id);
  const loadedCharacterIds = new Set(roomCharacters.map((character) => character.character_id));
  const loadedCharacters = characters.filter((character) => loadedCharacterIds.has(character.character_id));
  const chatToken = ownTokens.find((token) => token.token_id === chatTokenId);
  const chatTokenFace = chatToken?.faces?.find((face) => face.face_id === chatToken.presentation?.active_face_id);
  const chatTokenImage = chatTokenFace?.image_url ?? chatToken?.presentation?.image_url;

  if (!user || appView === "auth") {
    return <AuthPage
      errorMessage={errorMessage}
      mode={authMode}
      password={passwordInput}
      username={usernameInput}
      onModeChange={setAuthMode}
      onPasswordChange={setPasswordInput}
      onSubmit={handleAuthSubmit}
      onUsernameChange={setUsernameInput}
    />;
  }

  if (appView === "home") {
    return <>
      <HomePage
      connectionStatus={connectionStatus}
      displayName={nameInput}
      errorMessage={errorMessage}
      isLoadingRooms={isLoadingRooms}
      roomId={roomInput}
      rooms={rooms}
      user={user}
      onCreateRoom={handleCreateRoom}
      onDisplayNameChange={setNameInput}
      onJoinRoom={handleJoinRoom}
      onLogout={handleLogout}
      onOpenRoom={handleOpenRoom}
      onOpenKnowledgeBase={handleOpenKnowledgeBase}
      onOpenCharacters={() => setHomeCharactersOpen(true)}
      onRemoveRoom={handleRemoveRoom}
      onRoomIdChange={setRoomInput}
      onRefreshRooms={() => void loadMyRooms()}
      />
      {homeKnowledgeOpen && <KnowledgeBasePanel bases={knowledgeBases.filter((base) => base.kind === homeKnowledgeKind)} documents={knowledgeDocuments} selectedBaseId={selectedKnowledgeBaseId} selectedDocumentId={selectedDocumentId} name={knowledgeNameInput} kind={knowledgeKindInput} parentId={knowledgeParentIdInput} title={documentTitleInput} category={documentCategoryInput} content={documentContentInput} aiEnabled={documentAiEnabledInput} onClose={() => setHomeKnowledgeOpen(false)} onSelectBase={handleKnowledgeBaseChange} onSelectDocument={(document) => { setSelectedDocumentId(document.document_id); setDocumentTitleInput(document.title); setDocumentCategoryInput(document.category); setDocumentContentInput(document.content); setDocumentAiEnabledInput(document.ai_enabled !== false); }} onNewDocument={() => { setSelectedDocumentId(null); setDocumentTitleInput(""); setDocumentCategoryInput(""); setDocumentContentInput(""); setDocumentAiEnabledInput(true); }} onNameChange={setKnowledgeNameInput} onKindChange={setKnowledgeKindInput} onParentIdChange={setKnowledgeParentIdInput} onTitleChange={setDocumentTitleInput} onCategoryChange={setDocumentCategoryInput} onContentChange={setDocumentContentInput} onAiEnabledChange={setDocumentAiEnabledInput} onCreateBase={createKnowledgeBase} onSaveDocument={saveKnowledgeDocument} onDeleteBase={deleteKnowledgeBase} onDeleteDocument={deleteKnowledgeDocument} onImportFile={importKnowledgeFile} />}
      {homeCharactersOpen && <CharacterLibraryPanel characters={characters} name={characterNameInput} stText={characterStInput} selectedCharacterId={selectedCharacterId} onClose={() => setHomeCharactersOpen(false)} onNameChange={setCharacterNameInput} onStTextChange={setCharacterStInput} onImportSt={importStCharacter} onSelect={setSelectedCharacterId} onDelete={deleteCharacter} />}
    </>;
  }

  return (
    <main className="app-shell">
      <header className="room-appbar">
        <div className="room-appbar-start"><button type="button" className="back-to-home" onClick={handleLeaveRoom}>← 大厅</button><div><span className="eyebrow">COC-STAR / ROOM</span><h1>{activeScene?.name ?? "房间工作台"}</h1></div></div>
        <div className="room-appbar-actions"><button type="button" className={activeDrawer === "characters" ? "workspace-tool-button active-tool" : "workspace-tool-button"} onClick={() => setActiveDrawer((drawer) => drawer === "characters" ? "none" : "characters")}>我的角色</button>{self?.role === "gm" && <button type="button" className={activeDrawer === "knowledge" ? "workspace-tool-button active-tool" : "workspace-tool-button"} onClick={() => setActiveDrawer((drawer) => drawer === "knowledge" ? "none" : "knowledge")}>房间知识库</button>}{self?.role === "gm" && <button type="button" className={activeDrawer === "ai" ? "workspace-tool-button active-tool" : "workspace-tool-button"} onClick={() => setActiveDrawer((drawer) => drawer === "ai" ? "none" : "ai")}>AI 助手</button>}{self?.role === "gm" && <button type="button" className={activeDrawer === "scene" ? "workspace-tool-button active-tool" : "workspace-tool-button"} onClick={() => setActiveDrawer((drawer) => drawer === "scene" ? "none" : "scene")}>场景</button>}{self?.role === "gm" && <button type="button" className={activeDrawer === "audio" ? "workspace-tool-button active-tool" : "workspace-tool-button"} onClick={() => setActiveDrawer((drawer) => drawer === "audio" ? "none" : "audio")}>声音</button>}<button type="button" className={activeDrawer === "members" ? "workspace-tool-button active-tool" : "workspace-tool-button"} onClick={() => setActiveDrawer((drawer) => drawer === "members" ? "none" : "members")}>成员</button><div className="connection-status"><span className={`status-dot status-${connectionStatus}`} />{connectionStatusLabel(connectionStatus)}</div><button type="button" className="logout-button" onClick={handleLogout}>退出</button></div>
      </header>
      <form className="auth-controls legacy-editor" onSubmit={handleAuthSubmit}>
        <span className="auth-title">{authMode === "login" ? "账号登录" : "创建账号"}</span>
        <input aria-label="账号" placeholder="账号" value={usernameInput} onChange={(event) => setUsernameInput(event.target.value)} minLength={3} maxLength={32} />
        <input aria-label="密码" placeholder="密码（至少 8 位）" type="password" value={passwordInput} onChange={(event) => setPasswordInput(event.target.value)} minLength={8} maxLength={128} />
        <button type="submit">{authMode === "login" ? "登录" : "注册"}</button>
        <button type="button" className="secondary-button" onClick={() => setAuthMode(authMode === "login" ? "register" : "login")}>{authMode === "login" ? "切换注册" : "已有账号"}</button>
      </form>
      <form className="room-controls legacy-editor" onSubmit={handleJoinRoom}>
        <label>房间号<input value={roomInput} onChange={(event) => setRoomInput(event.target.value)} /></label>
        <label>玩家名<input value={nameInput} onChange={(event) => setNameInput(event.target.value)} /></label>
        <button type="button" onClick={handleCreateRoom} disabled={!user}>创建房间</button>
        <button type="submit" disabled={!user}>{connectionStatus === "connecting" ? "连接中…" : "加入房间"}</button>
        {!user && <span className="error-message">请先登录后进入房间</span>}
        {errorMessage && <span className="error-message">{errorMessage}</span>}
      </form>
      {self?.role === "gm" && <RoomDrawer title="房间 AI 助手" open={activeDrawer === "ai"} onClose={() => setActiveDrawer("none")}><RoomAiPanel config={aiConfig} providers={aiProviders} logs={aiLogs} providerName={providerNameInput} providerBaseUrl={providerBaseUrlInput} providerModel={providerModelInput} providerApiKey={providerApiKeyInput} onConfigChange={setAiConfig} onProviderNameChange={setProviderNameInput} onProviderBaseUrlChange={setProviderBaseUrlInput} onProviderModelChange={setProviderModelInput} onProviderApiKeyChange={setProviderApiKeyInput} onSaveConfig={saveRoomAiConfig} onSaveProvider={saveAiProvider} /></RoomDrawer>}
      {self?.role === "gm" && <RoomDrawer title="房间知识库挂载" open={activeDrawer === "knowledge"} onClose={() => setActiveDrawer("none")}><RoomKnowledgePanel bases={knowledgeBases} mountedIds={roomMountedKnowledgeIds} onMountedIdsChange={setRoomMountedKnowledgeIds} onSave={() => void saveRoomKnowledge()} /></RoomDrawer>}
      <RoomDrawer title="我的角色" open={activeDrawer === "characters"} onClose={() => setActiveDrawer("none")}>
        <RoomCharacterPanel characters={characters} roomCharacters={roomCharacters} onLoad={(characterId) => void loadCharacterIntoRoom(characterId)} />
        <div className="drawer-token-list"><div className="drawer-section-heading"><span>我的 Token</span><button type="button" onClick={handleAddToken}>新建</button></div>{ownTokens.map((token) => <button type="button" key={token.token_id} className={token.token_id === selectedTokenId ? "drawer-list-item drawer-list-item-active" : "drawer-list-item"} onClick={() => setSelectedTokenId(token.token_id)}><span className="drawer-token-swatch" style={{ background: token.presentation?.image_url ? `url(${token.presentation.image_url}) center / cover` : token.color }} />{token.name}<small>{token.presentation?.image_url ? "角色" : "NPC"}</small></button>)}{ownTokens.length === 0 && <p className="empty-copy">还没有自己的 Token。新建后可上传立绘与差分。</p>}</div>
        {canEditSelectedToken && selectedToken ? <TokenEditor characters={loadedCharacters} token={selectedToken} tokenNameInput={tokenNameInput} tokenScaleInput={tokenScaleInput} tokenShapeInput={tokenShapeInput} tokenCharacterIdInput={tokenCharacterIdInput} faceLabelInput={faceLabelInput} faceTriggerInput={faceTriggerInput} onNameChange={setTokenNameInput} onScaleChange={setTokenScaleInput} onShapeChange={setTokenShapeInput} onCharacterChange={setTokenCharacterIdInput} onImageChange={setTokenImageFile} onSave={handleSaveToken} onFaceLabelChange={setFaceLabelInput} onFaceTriggerChange={setFaceTriggerInput} onFaceImageChange={setFaceImageFile} onAddFace={handleAddFace} onRemoveFace={handleRemoveFace} /> : <p className="drawer-hint">选择一个自己的 Token 后，在这里编辑立绘与差分。</p>}
      </RoomDrawer>
      {self?.role === "gm" && <RoomDrawer title="场景与图层" open={activeDrawer === "scene"} onClose={() => setActiveDrawer("none")}>
        <form className="scene-form" onSubmit={handleCreateScene}><input aria-label="场景名称" placeholder="新场景名称" value={sceneNameInput} onChange={(event) => setSceneNameInput(event.target.value)} /><input aria-label="背景图地址" placeholder="背景图 URL（可选）" value={sceneBackgroundInput} onChange={(event) => setSceneBackgroundInput(event.target.value)} /><button type="submit">创建场景</button></form>
        <div className="drawer-scene-list">{scenes.map((scene) => <button type="button" key={scene.scene_id} className={scene.is_active ? "drawer-list-item drawer-list-item-active" : "drawer-list-item"} onClick={() => handleActivateScene(scene.scene_id)}>{scene.name}<small>{scene.is_active ? "当前舞台" : "切换"}</small></button>)}</div>
        <div className="drawer-section-heading"><span>图层</span><small>{sceneLayers.length} 项</small></div>
        <form className="scene-layer-form" onSubmit={handleAddLayer}><select aria-label="图层类型" value={layerTypeInput} onChange={(event) => setLayerTypeInput(event.target.value as SceneLayer["layer_type"])}><option value="background">背景</option><option value="foreground">前景</option><option value="panel">屏幕面板</option><option value="marker">标记</option></select><input aria-label="图层名称" placeholder="图层名称" value={layerNameInput} onChange={(event) => setLayerNameInput(event.target.value)} /><select aria-label="图层形状" value={layerShapeInput} onChange={(event) => setLayerShapeInput(event.target.value as SceneLayer["shape"])}><option value="rectangle">矩形</option><option value="square">正方形</option><option value="circle">圆形</option></select><select aria-label="图片适配" value={layerFitInput} onChange={(event) => setLayerFitInput(event.target.value as SceneLayer["image_fit"])}><option value="cover">裁剪填充</option><option value="contain">完整显示</option><option value="fill">拉伸填充</option></select><input aria-label="背景虚化" type="number" min="0" max="24" step="1" placeholder="虚化 px" value={layerBlurInput} onChange={(event) => setLayerBlurInput(event.target.value)} /><input aria-label="图层透明度" type="number" min="0.05" max="1" step="0.05" value={layerOpacityInput} onChange={(event) => setLayerOpacityInput(event.target.value)} /><input aria-label="标记文字" placeholder="标记文字（可选）" value={layerTextInput} onChange={(event) => setLayerTextInput(event.target.value)} /><input aria-label="图层图片" type="file" accept="image/png,image/jpeg,image/webp,image/gif" onChange={(event) => setLayerImageFile(event.target.files?.[0] ?? null)} /><button type="submit">添加图层</button></form>
        <div className="scene-layer-list">{sceneLayers.map((layer) => <div className="scene-layer-row" key={layer.layer_id}><span>{layer.name}</span><small>{layer.layer_type}</small><button type="button" onClick={() => handleToggleLayer(layer)}>{layer.visible ? "隐藏" : "显示"}</button><button type="button" onClick={() => handleRemoveLayer(layer)}>删除</button></div>)}</div>
        {sceneLayers.length > 0 && <div className="layer-nudge"><label>调整图层<select value={selectedLayerId ?? ""} onChange={(event) => setSelectedLayerId(event.target.value || null)}><option value="">选择图层</option>{sceneLayers.map((layer) => <option value={layer.layer_id} key={layer.layer_id}>{layer.name}</option>)}</select></label><div className="nudge-buttons"><button type="button" onClick={() => handleNudgeLayer(0, -0.02)}>上</button><button type="button" onClick={() => handleNudgeLayer(-0.02, 0)}>左</button><button type="button" onClick={() => handleNudgeLayer(0.02, 0)}>右</button><button type="button" onClick={() => handleNudgeLayer(0, 0.02)}>下</button></div></div>}
      </RoomDrawer>}
      <RoomDrawer title="骰子配置" open={activeDrawer === "dice"} onClose={() => setActiveDrawer("none")}><DiceConfigPanel shortcuts={diceShortcuts} onChange={setDiceShortcuts} /></RoomDrawer>
      {self?.role === "gm" && <RoomDrawer title="声音与 BGM" open={activeDrawer === "audio"} onClose={() => setActiveDrawer("none")}>
        <form className="bgm-upload-form" onSubmit={handleAddBgm}><select value={bgmSlotInput} onChange={(event) => setBgmSlotInput(event.target.value as BgmSlot)} aria-label="BGM 槽位"><option value="bgm01">BGM01</option><option value="bgm02">BGM02</option></select><input value={bgmNameInput} onChange={(event) => setBgmNameInput(event.target.value)} placeholder="曲目名称（可选，默认文件名）" aria-label="曲目名称" /><input type="file" accept="audio/mpeg,audio/ogg,audio/wav,audio/mp4,audio/aac,audio/flac,audio/webm" onChange={(event) => setBgmFile(event.target.files?.[0] ?? null)} aria-label="BGM 音频" /><button type="submit">上传到槽位</button>{bgmUploadStatus && <small className="drawer-hint">{bgmUploadStatus}</small>}</form>
        <div className="bgm-list">{(["bgm01", "bgm02"] as BgmSlot[]).map((slot) => { const track = bgmTracks.find((item) => item.slot === slot); const playback = bgmPlayback.find((item) => item.slot === slot); return <div className="bgm-row" key={slot}><div className="bgm-info"><strong>{slot.toUpperCase()}</strong><span>{track?.name ?? "未设置曲目"}</span></div><div className="bgm-controls"><button type="button" disabled={!track} onClick={() => handleBgmControl(slot, "play")}>播放</button><button type="button" disabled={!track} onClick={() => handleBgmControl(slot, "pause")}>暂停</button><button type="button" disabled={!track} onClick={() => handleBgmControl(slot, "stop")}>停止</button>{track && <button type="button" onClick={() => socketRef.current?.send(JSON.stringify({ type: "bgm.track.remove", bgm_id: track.bgm_id }))}>移除</button>}<input type="range" min="0" max="1" step="0.05" value={bgmVolume[slot]} onChange={(event) => handleBgmVolume(slot, Number(event.target.value))} aria-label={`${slot} 音量`} /><button type="button" onClick={() => handleBgmMute(slot)}>{bgmMuted[slot] ? "取消静音" : "静音"}</button><small>{playback?.is_playing ? "播放中" : "已暂停"}</small></div></div>; })}</div>
      </RoomDrawer>}
      <RoomDrawer title="房间成员" open={activeDrawer === "members"} onClose={() => setActiveDrawer("none")}>
        <div className="drawer-room-id"><span>房间号</span><strong>{roomId}</strong></div><form className="member-name-form" onSubmit={handleMemberNameUpdate}><label>我的房间昵称<input value={memberNameInput} onChange={(event) => setMemberNameInput(event.target.value)} maxLength={40} /><small>这个名字会显示在成员列表和普通发言中</small></label><button type="submit">保存昵称</button></form><div className="player-list">{members.map((member) => <MemberRow key={member.user_id} member={member} self={member.user_id === self?.user_id} canManage={self?.role === "gm"} onRoleUpdate={handleMemberRoleUpdate} onRemove={handleMemberRemove} />)}{members.length === 0 && <p className="empty-copy">还没有其他成员加入。</p>}</div>
      </RoomDrawer>
      <section className={`workspace ${chatCollapsed ? "workspace-chat-collapsed" : ""}`}>
        <aside className="sidebar">
          <div className="panel-heading"><span>房间成员</span><span className="muted">{members.length} / 8</span></div>
          <div className="player-list">
            {members.map((member) => <MemberRow key={member.user_id} member={member} self={member.user_id === self?.user_id} canManage={self?.role === "gm"} onRoleUpdate={handleMemberRoleUpdate} onRemove={handleMemberRemove} />)}
            {members.length === 0 && <p className="empty-copy">加入房间后会显示在线成员</p>}
          </div>
          <div className="sidebar-note"><span>当前房间</span><p>{roomId}</p></div>
        </aside>
        <section className="board-area">
          <div className="board-toolbar"><div><span className="toolbar-kicker">当前舞台</span><span className="toolbar-title">{activeScene?.name ?? "未选择场景"}</span></div><div className="toolbar-actions"><button type="button" onClick={handleAddToken}>添加 Token</button>{self?.role === "gm" && <button type="button" onClick={() => setActiveDrawer("scene")}>编辑场景</button>}</div></div>
          {self?.role === "gm" && <form className="scene-form" onSubmit={handleCreateScene}><input aria-label="场景名称" placeholder="新场景名称" value={sceneNameInput} onChange={(event) => setSceneNameInput(event.target.value)} /><input aria-label="背景图地址" placeholder="背景图 URL（可选）" value={sceneBackgroundInput} onChange={(event) => setSceneBackgroundInput(event.target.value)} /><button type="submit">创建场景</button></form>}
          {self?.role === "gm" && <form className="scene-layer-form" onSubmit={handleAddLayer}><select aria-label="图层类型" value={layerTypeInput} onChange={(event) => setLayerTypeInput(event.target.value as SceneLayer["layer_type"])}><option value="background">背景</option><option value="foreground">前景</option><option value="panel">屏幕面板</option><option value="marker">标记</option></select><input aria-label="图层名称" placeholder="图层名称" value={layerNameInput} onChange={(event) => setLayerNameInput(event.target.value)} /><input aria-label="标记文字" placeholder="标记文字（可选）" value={layerTextInput} onChange={(event) => setLayerTextInput(event.target.value)} /><input aria-label="图层图片" type="file" accept="image/png,image/jpeg,image/webp,image/gif" onChange={(event) => setLayerImageFile(event.target.files?.[0] ?? null)} /><button type="submit">添加图层</button></form>}
          {sceneLayers.length > 0 && <div className="scene-layer-list">{sceneLayers.map((layer) => <div className="scene-layer-row" key={layer.layer_id}><span>{layer.name}</span><small>{layer.layer_type}</small>{self?.role === "gm" && <><button type="button" onClick={() => handleToggleLayer(layer)}>{layer.visible ? "隐藏" : "显示"}</button><button type="button" onClick={() => handleRemoveLayer(layer)}>删除</button></>}</div>)}</div>}
          <section className="bgm-panel"><div className="panel-heading"><span>BGM 播放</span><span className="muted">房间同步 / 本地音量</span></div>{self?.role === "gm" && <form className="bgm-upload-form" onSubmit={handleAddBgm}><select value={bgmSlotInput} onChange={(event) => setBgmSlotInput(event.target.value as BgmSlot)} aria-label="BGM 槽位"><option value="bgm01">BGM01</option><option value="bgm02">BGM02</option></select><input value={bgmNameInput} onChange={(event) => setBgmNameInput(event.target.value)} placeholder="曲目名称（可选，默认文件名）" aria-label="曲目名称" /><input type="file" accept="audio/mpeg,audio/ogg,audio/wav,audio/mp4,audio/aac,audio/flac,audio/webm" onChange={(event) => setBgmFile(event.target.files?.[0] ?? null)} aria-label="BGM 音频" /><button type="submit">上传到槽位</button>{bgmUploadStatus && <small className="drawer-hint">{bgmUploadStatus}</small>}</form>}<div className="bgm-list">{(["bgm01", "bgm02"] as BgmSlot[]).map((slot) => { const track = bgmTracks.find((item) => item.slot === slot); const playback = bgmPlayback.find((item) => item.slot === slot); return <div className="bgm-row" key={slot}><div className="bgm-info"><strong>{slot.toUpperCase()}</strong><span>{track?.name ?? "未设置曲目"}</span></div><div className="bgm-controls">{self?.role === "gm" && <><button type="button" disabled={!track} onClick={() => handleBgmControl(slot, "play")}>播放</button><button type="button" disabled={!track} onClick={() => handleBgmControl(slot, "pause")}>暂停</button><button type="button" disabled={!track} onClick={() => handleBgmControl(slot, "stop")}>停止</button>{track && <button type="button" onClick={() => socketRef.current?.send(JSON.stringify({ type: "bgm.track.remove", bgm_id: track.bgm_id }))}>移除</button>}</>}<input type="range" min="0" max="1" step="0.05" value={bgmVolume[slot]} onChange={(event) => handleBgmVolume(slot, Number(event.target.value))} aria-label={`${slot} 音量`} /><button type="button" onClick={() => handleBgmMute(slot)}>{bgmMuted[slot] ? "取消静音" : "静音"}</button><small>{playback?.is_playing ? "播放中" : "已暂停"}</small></div></div>; })}</div></section>
          {canEditSelectedToken && selectedToken && <TokenEditor characters={loadedCharacters} token={selectedToken} tokenNameInput={tokenNameInput} tokenScaleInput={tokenScaleInput} tokenShapeInput={tokenShapeInput} tokenCharacterIdInput={tokenCharacterIdInput} faceLabelInput={faceLabelInput} faceTriggerInput={faceTriggerInput} onNameChange={setTokenNameInput} onScaleChange={setTokenScaleInput} onShapeChange={setTokenShapeInput} onCharacterChange={setTokenCharacterIdInput} onImageChange={setTokenImageFile} onSave={handleSaveToken} onFaceLabelChange={setFaceLabelInput} onFaceTriggerChange={setFaceTriggerInput} onFaceImageChange={setFaceImageFile} onAddFace={handleAddFace} onRemoveFace={handleRemoveFace} />}
          <div className="quick-tools"><button type="button" onClick={handleAddToken}>Token</button><button type="button" onClick={() => handleFocusTool(".scene-layer-form")}>图层</button><button type="button" onClick={() => handleFocusTool(".bgm-panel")}>音乐</button><button type="button" onClick={() => handleFocusTool(".chat-composer")}>发言</button></div>
          {self?.role === "gm" && sceneLayers.length > 0 && <div className="layer-nudge"><label>调整图层<select value={selectedLayerId ?? ""} onChange={(event) => setSelectedLayerId(event.target.value || null)}><option value="">选择图层</option>{sceneLayers.map((layer) => <option value={layer.layer_id} key={layer.layer_id}>{layer.name}</option>)}</select></label><div className="nudge-buttons"><button type="button" onClick={() => handleNudgeLayer(0, -0.02)}>上</button><button type="button" onClick={() => handleNudgeLayer(-0.02, 0)}>左</button><button type="button" onClick={() => handleNudgeLayer(0.02, 0)}>右</button><button type="button" onClick={() => handleNudgeLayer(0, 0.02)}>下</button></div><small>每次移动 2%</small></div>}
          {stageMessage && <div className="stage-dialogue"><div className="stage-portrait" style={stageImage ? { backgroundImage: `url(${stageImage})` } : { background: stageToken?.color ?? "#d7b56d" }}>{stageImage ? "" : (stageMessage.character_name || stageMessage.display_name).slice(0, 1)}</div><div className="stage-dialogue-body"><strong style={{ color: stageMessage.character_color ?? "#f0dca9" }}>{stageMessage.character_name || stageMessage.display_name}</strong><p>{stageMessage.text}</p></div></div>}
          <div className="board" ref={boardRef} style={activeScene?.background_url ? { backgroundImage: `linear-gradient(#10121866, #10121866), url(${activeScene.background_url})`, backgroundSize: "cover", backgroundPosition: "center" } : undefined}><div className="board-grid" />{sceneLayers.filter((layer) => layer.visible).map((layer) => <div className={`scene-layer scene-layer-${layer.layer_type} scene-layer-shape-${layer.shape} ${self?.role === "gm" ? "scene-layer-editable" : ""} ${selectedLayerId === layer.layer_id ? "scene-layer-selected" : ""}`} key={layer.layer_id} style={{ left: `${layer.x * 100}%`, top: `${layer.y * 100}%`, width: `${layer.width * 100}%`, height: `${layer.height * 100}%`, zIndex: layer.layer_type === "background" ? 0 : Math.max(layer.z_index, 2), opacity: layer.opacity, filter: layer.blur > 0 ? `blur(${layer.blur}px)` : undefined, backgroundImage: layer.image_url ? `url(${layer.image_url})` : undefined, backgroundSize: layer.image_fit, backgroundColor: layer.image_url ? undefined : "#242b38" }} onPointerDown={(event) => handleLayerPointerDown(layer, "move", event)} onPointerMove={handleLayerPointerMove} onPointerUp={handleLayerPointerUp} title={self?.role === "gm" ? "拖动移动图层，拖右下角调整大小" : layer.name}>{layer.text}{self?.role === "gm" && selectedLayerId === layer.layer_id && <span className="scene-layer-resize" onPointerDown={(event) => handleLayerPointerDown(layer, "resize", event)} />}</div>)}<div className="board-location">{activeScene?.name ?? "未选择场景"}</div>{tokens.map((token) => { const face = token.faces?.find((item) => item.face_id === token.presentation?.active_face_id); const imageUrl = face?.image_url ?? token.presentation?.image_url; const tokenSize = 56 * (token.presentation?.scale ?? 1); const displayShape = selectedTokenId === token.token_id ? tokenShapeInput : token.shape; return <button className={`token token-shape-${displayShape} ${selectedTokenId === token.token_id ? "token-selected" : ""}`} key={token.token_id} draggable style={{ left: `${token.x * 100}%`, top: `${token.y * 100}%`, width: `${tokenSize}px`, height: `${tokenSize}px`, borderRadius: displayShape === "circle" ? "50%" : "8px", background: imageUrl ? `url(${imageUrl}) center / cover` : token.color }} onClick={() => setSelectedTokenId(token.token_id)} onDragEnd={(event) => handleMoveToken(token, event)} onDoubleClick={() => handleRemoveToken(token.token_id)} title="点击编辑，拖动移动，双击删除">{imageUrl ? "" : token.name.slice(0, 1)}</button>; })}{tokens.length === 0 && <div className="board-empty-state"><span className="empty-icon">✦</span><strong>虚拟桌面准备就绪</strong><p>点击“添加棋子”，创建第一个可同步角色</p></div>}</div>
        </section>
        <ChatPanel
          collapsed={chatCollapsed}
          tabs={chatTabs}
          activeTabId={chatTabId}
          onToggleCollapsed={() => setChatCollapsed((collapsed) => !collapsed)}
          onTabChange={setChatTabId}
          showChannelForm={showChannelForm}
          onToggleChannelForm={() => setShowChannelForm((shown) => !shown)}
          channelName={channelNameInput}
          onChannelNameChange={setChannelNameInput}
          channelDialogue={channelDialogueInput}
          onChannelDialogueChange={setChannelDialogueInput}
          onCreateChannel={handleCreateChatTab}
          messages={visibleMessages}
          ownTokens={ownTokens}
          selectedTokenId={chatTokenId}
          onTokenChange={handleChatTokenChange}
          selectedFaceId={chatFaceId}
          onFaceChange={handleChatFaceChange}
          selectedTokenFaces={chatToken?.faces ?? []}
          selectedTokenImage={chatTokenImage}
          selectedTokenColor={chatToken?.color}
          diceShortcuts={diceShortcuts}
          onOpenDiceConfig={() => setActiveDrawer("dice")}
          chatName={chatNameInput}
          onChatNameChange={setChatNameInput}
          chatColor={chatColorInput}
          onChatColorChange={setChatColorInput}
          message={messageInput}
          onMessageChange={setMessageInput}
          onSend={handleSendMessage}
        />
      </section>
    </main>
  );
}

interface ChatPanelProps {
  collapsed: boolean;
  tabs: ChatTab[];
  activeTabId: string | null;
  onToggleCollapsed: () => void;
  onTabChange: (tabId: string) => void;
  showChannelForm: boolean;
  onToggleChannelForm: () => void;
  channelName: string;
  onChannelNameChange: (value: string) => void;
  channelDialogue: boolean;
  onChannelDialogueChange: (value: boolean) => void;
  onCreateChannel: (event: FormEvent) => void;
  messages: ChatMessage[];
  ownTokens: BoardToken[];
  selectedTokenId: string | null;
  onTokenChange: (tokenId: string | null) => void;
  selectedFaceId: string | null;
  onFaceChange: (faceId: string) => void;
  selectedTokenFaces: TokenFace[];
  selectedTokenImage?: string | null;
  selectedTokenColor?: string;
  diceShortcuts: DiceShortcut[];
  onOpenDiceConfig: () => void;
  chatName: string;
  onChatNameChange: (value: string) => void;
  chatColor: string;
  onChatColorChange: (value: string) => void;
  message: string;
  onMessageChange: (value: string) => void;
  onSend: (event: FormEvent) => void;
}

function ChatPanel({ collapsed, tabs, activeTabId, onToggleCollapsed, onTabChange, showChannelForm, onToggleChannelForm, channelName, onChannelNameChange, channelDialogue, onChannelDialogueChange, onCreateChannel, messages, ownTokens, selectedTokenId, onTokenChange, selectedFaceId, onFaceChange, selectedTokenFaces, selectedTokenImage, selectedTokenColor, diceShortcuts, onOpenDiceConfig, chatName, onChatNameChange, chatColor, onChatColorChange, message, onMessageChange, onSend }: ChatPanelProps) {
  const [showFacePickerLocal, setShowFacePickerLocal] = useState(false);
  return <aside className={`chat-panel ${collapsed ? "chat-panel-collapsed" : ""}`}>
    <div className="chat-panel-header"><span>聊天频道</span><button type="button" aria-expanded={!collapsed} aria-label={collapsed ? "展开聊天频道" : "收起聊天频道"} onClick={onToggleCollapsed}>{collapsed ? "展开" : "收起"}</button></div>
    {!collapsed && <>
      <div className="chat-tabs">{tabs.map((tab) => <button type="button" key={tab.tab_id} className={tab.tab_id === activeTabId ? "active-chat-tab" : ""} onClick={() => onTabChange(tab.tab_id)}>{tab.name}</button>)}<button type="button" className="chat-tab-add" onClick={onToggleChannelForm}>＋</button></div>
      {showChannelForm && <form className="channel-form" onSubmit={onCreateChannel}><input value={channelName} onChange={(event) => onChannelNameChange(event.target.value)} placeholder="频道名称" maxLength={40} /><label><input type="checkbox" checked={channelDialogue} onChange={(event) => onChannelDialogueChange(event.target.checked)} />开启立绘对话</label><button type="submit">添加</button></form>}
      <div className="message-list">{messages.map((item) => <MessageRow key={item.message_id} message={item} />)}{messages.length === 0 && <p className="empty-copy">当前频道还没有消息</p>}</div>
      <div className="chat-identity"><button type="button" className={`chat-portrait ${selectedTokenId ? "chat-portrait-clickable" : ""}`} onClick={() => selectedTokenFaces.length > 0 && setShowFacePickerLocal((value) => !value)} style={selectedTokenImage ? { backgroundImage: `url(${selectedTokenImage})` } : { background: selectedTokenColor ?? "#3a4050" }} aria-label="打开 Token 差分">{selectedTokenImage ? "" : "无"}</button><select aria-label="选择角色卡" value={selectedTokenId ?? ""} onChange={(event) => onTokenChange(event.target.value || null)}><option value="">☰ 无（不使用角色卡）</option>{ownTokens.map((token) => <option value={token.token_id} key={token.token_id}>☰ {token.name}</option>)}</select><input aria-label="发言名称" value={chatName} onChange={(event) => onChatNameChange(event.target.value)} maxLength={40} /><input className="chat-color-picker" aria-label="名字颜色" type="color" value={chatColor} onChange={(event) => onChatColorChange(event.target.value)} /></div>
      {showFacePickerLocal && selectedTokenFaces.length > 0 && <div className="chat-face-picker"><button type="button" className={!selectedFaceId ? "active-face" : ""} onClick={() => onFaceChange("")}>默认</button>{selectedTokenFaces.map((face) => <button type="button" className={face.face_id === selectedFaceId ? "active-face" : ""} key={face.face_id} onClick={() => onFaceChange(face.face_id)}><img src={face.image_url} alt={face.label} /><span>{face.label}</span></button>)}</div>}
      <div className="dice-shortcuts">{diceShortcuts.map((shortcut) => <button type="button" key={shortcut.id} onClick={() => onMessageChange(`/r ${shortcut.expression}`)}>◇ {shortcut.label}</button>)}<button type="button" className="dice-config-button" onClick={onOpenDiceConfig} aria-label="打开骰子配置">⚙</button></div>
      <form className="chat-composer" onSubmit={onSend}><input aria-label="聊天消息" placeholder="输入消息…" value={message} onChange={(event) => onMessageChange(event.target.value)} /><button type="submit">发送</button></form>
    </>}
  </aside>;
}

function connectionStatusLabel(status: string) {
  return { disconnected: "未连接", connecting: "连接中", connected: "已连接", error: "连接异常" }[status] ?? status;
}

interface TokenEditorProps {
  characters: CharacterSummary[];
  faceLabelInput: string;
  faceTriggerInput: string;
  onAddFace: (event: FormEvent) => void;
  onFaceImageChange: (file: File | null) => void;
  onFaceLabelChange: (value: string) => void;
  onFaceTriggerChange: (value: string) => void;
  onImageChange: (file: File | null) => void;
  onNameChange: (value: string) => void;
  onRemoveFace: (face: TokenFace) => void;
  onSave: (event: FormEvent) => void;
  onScaleChange: (value: string) => void;
  onShapeChange: (value: BoardToken["shape"]) => void;
  onCharacterChange: (value: string | null) => void;
  token: BoardToken;
  tokenNameInput: string;
  tokenScaleInput: string;
  tokenShapeInput: BoardToken["shape"];
  tokenCharacterIdInput: string | null;
}

function TokenEditor({ characters, faceLabelInput, faceTriggerInput, onAddFace, onFaceImageChange, onFaceLabelChange, onFaceTriggerChange, onImageChange, onNameChange, onRemoveFace, onSave, onScaleChange, onShapeChange, onCharacterChange, token, tokenNameInput, tokenScaleInput, tokenShapeInput, tokenCharacterIdInput }: TokenEditorProps) {
  return <section className="token-editor"><div className="token-editor-heading"><strong>Token 编辑</strong><span>{tokenCharacterIdInput ? "角色卡" : token.presentation?.image_url ? "角色" : "NPC"}</span></div><form className="token-editor-form" onSubmit={onSave}><label>名称<input value={tokenNameInput} onChange={(event) => onNameChange(event.target.value)} maxLength={40} /></label><label>Token 形状<select value={tokenShapeInput} onChange={(event) => onShapeChange(event.target.value as BoardToken["shape"])}><option value="circle">圆形</option><option value="square">方形</option></select></label><label>绑定角色卡<select value={tokenCharacterIdInput ?? ""} onChange={(event) => onCharacterChange(event.target.value || null)}><option value="">不绑定角色卡</option>{characters.map((character) => <option key={character.character_id} value={character.character_id}>{character.name}</option>)}</select></label><label>大小<input type="number" min="0.25" max="4" step="0.25" value={tokenScaleInput} onChange={(event) => onScaleChange(event.target.value)} /></label><label>立绘<input type="file" accept="image/png,image/jpeg,image/webp,image/gif" onChange={(event) => onImageChange(event.target.files?.[0] ?? null)} /></label><button type="submit">保存 Token</button></form><div className="face-editor"><span className="face-editor-title">自定义差分</span><form onSubmit={onAddFace}><label>差分名称<input aria-label="差分名称" placeholder="例如：哭泣" value={faceLabelInput} onChange={(event) => onFaceLabelChange(event.target.value)} maxLength={80} /></label><label>触发关键词<input aria-label="差分触发关键词" placeholder="例如：哭泣" value={faceTriggerInput} onChange={(event) => onFaceTriggerChange(event.target.value)} maxLength={80} /></label><input aria-label="差分图片" type="file" accept="image/png,image/jpeg,image/webp,image/gif" onChange={(event) => onFaceImageChange(event.target.files?.[0] ?? null)} /><button type="submit">添加差分</button></form><div className="face-list">{(token.faces ?? []).map((face) => <div className="face-row" key={face.face_id}><img src={face.image_url} alt={face.label} /><span>{face.label} · #{face.trigger ?? face.label}</span><button type="button" onClick={() => onRemoveFace(face)}>删除</button></div>)}{(token.faces ?? []).length === 0 && <small>还没有差分。发言末尾输入 #关键词 或 @关键词 会切换差分，并隐藏指令。</small>}</div></div></section>;
}

interface MemberRowProps {
  canManage: boolean;
  member: RoomMember;
  onRemove: (userId: string) => void;
  onRoleUpdate: (userId: string, role: "gm" | "player") => void;
  self: boolean;
}

function MemberRow({ canManage, member, onRemove, onRoleUpdate, self }: MemberRowProps) {
  return <div className="player"><span className="avatar">{member.display_name.slice(0, 1)}</span><span className="player-info"><strong>{member.display_name}{self ? "（我）" : ""}</strong><small>{member.role === "gm" ? "GM" : "玩家"}</small></span>{canManage && !self && <span className="member-actions"><button type="button" onClick={() => onRoleUpdate(member.user_id, member.role === "gm" ? "player" : "gm")} aria-label={member.role === "gm" ? `降级${member.display_name}` : `提升${member.display_name}`}>{member.role === "gm" ? "降级" : "GM"}</button><button type="button" onClick={() => onRemove(member.user_id)} aria-label={`移除${member.display_name}`}>移除</button></span>}</div>;
}

function MessageRow({ message }: { message: ChatMessage }) {
  const displayName = message.character_name || message.display_name;
  return <article className="message"><div className="message-meta"><strong style={{ color: message.character_color ?? "#d7b56d" }}>{displayName}</strong><time>刚刚</time></div><p>{message.text}</p></article>;
}

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(Math.max(value, minimum), maximum);
}
