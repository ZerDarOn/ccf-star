import { useEffect, useRef, useState } from "react";
import type { DragEvent, FormEvent } from "react";
import { AccountUser, useAuthStore } from "./authStore";
import { BgmPlayback, BgmSlot, BgmTrack, BoardToken, ChatMessage, ChatTab, RoomMember, RoomScene, SceneLayer, TokenFace, TokenPresentation, useRoomStore } from "./roomStore";

type RoomEvent =
  | { type: "room.connected"; room_id: string; self: RoomMember; members: RoomMember[]; board: { tokens: BoardToken[] }; scenes: RoomScene[]; active_scene: RoomScene | null; scene_layers: SceneLayer[]; bgm_tracks: BgmTrack[]; bgm_playback: BgmPlayback[]; chat_tabs: ChatTab[] }
  | { type: "member.joined"; member: RoomMember }
  | { type: "member.left"; user_id: string }
  | { type: "member.role.updated"; member: RoomMember }
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

const websocketBaseUrl = import.meta.env.VITE_API_WS_URL ?? "ws://127.0.0.1:8000";
const apiBaseUrl = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

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

export function App() {
  const socketRef = useRef<WebSocket | null>(null);
  const boardRef = useRef<HTMLDivElement | null>(null);
  const audioRefs = useRef<Record<BgmSlot, HTMLAudioElement | null>>({ bgm01: null, bgm02: null });
  const [roomInput, setRoomInput] = useState("demo-room");
  const [nameInput, setNameInput] = useState("苏鸣澈");
  const [messageInput, setMessageInput] = useState("");
  const [chatTabId, setChatTabId] = useState<string | null>(null);
  const [chatNameInput, setChatNameInput] = useState("");
  const [chatColorInput, setChatColorInput] = useState("#d7b56d");
  const [chatTokenId, setChatTokenId] = useState<string | null>(null);
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
  const [faceImageFile, setFaceImageFile] = useState<File | null>(null);
  const [layerTypeInput, setLayerTypeInput] = useState<SceneLayer["layer_type"]>("panel");
  const [layerNameInput, setLayerNameInput] = useState("");
  const [layerTextInput, setLayerTextInput] = useState("");
  const [layerImageFile, setLayerImageFile] = useState<File | null>(null);
  const [selectedLayerId, setSelectedLayerId] = useState<string | null>(null);
  const [bgmSlotInput, setBgmSlotInput] = useState<BgmSlot>("bgm01");
  const [bgmNameInput, setBgmNameInput] = useState("");
  const [bgmFile, setBgmFile] = useState<File | null>(null);
  const [bgmVolume, setBgmVolume] = useState<Record<BgmSlot, number>>({ bgm01: 0.8, bgm02: 0.8 });
  const [bgmMuted, setBgmMuted] = useState<Record<BgmSlot, boolean>>({ bgm01: false, bgm02: false });
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [usernameInput, setUsernameInput] = useState("");
  const [passwordInput, setPasswordInput] = useState("");
  const { accessToken, refreshToken, user, setSession, clearSession } = useAuthStore();
  const { connectionStatus, errorMessage, members, messages, chatTabs, self, roomId, tokens, scenes, activeScene, sceneLayers, bgmTracks, bgmPlayback, setConnectionStatus, setRoomSnapshot, setBoardSnapshot, setChatTabs, upsertChatTab, setSceneSnapshot, setSceneLayers, upsertSceneLayer, removeSceneLayer, updateScene, activateScene, addMember, updateMember, removeMember, addMessage, upsertToken, removeToken, updateTokenPresentation, upsertTokenFace, removeTokenFace, setBgmSnapshot, upsertBgmTrack, removeBgmTrack, setBgmPlayback, setErrorMessage } = useRoomStore();

  useEffect(() => () => socketRef.current?.close(), []);

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
      const audio = currentAudio ?? new Audio(track.audio_url);
      if (!currentAudio || currentAudio.src !== track.audio_url) {
        currentAudio?.pause();
        audio.src = track.audio_url;
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
  }, [selectedTokenId, tokens]);

  useEffect(() => {
    if (self && !chatNameInput) setChatNameInput(self.display_name);
    if (!chatTabId && chatTabs.length > 0) setChatTabId(chatTabs.find((tab) => tab.tab_type === "main")?.tab_id ?? chatTabs[0].tab_id);
  }, [self, chatTabs, chatNameInput, chatTabId]);

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
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "账号操作失败");
    }
  };

  const handleLogout = () => {
    socketRef.current?.close();
    clearSession();
    setConnectionStatus("disconnected");
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

  const handleJoinRoom = async (event: FormEvent) => {
    event.preventDefault();
    const nextRoomId = roomInput.trim();
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

  const handleRoomEvent = (rawEvent: string) => {
    try {
      const event = JSON.parse(rawEvent) as RoomEvent;
      if (event.type === "room.connected") { setConnectionStatus("connected"); setRoomSnapshot(event.room_id, event.self, event.members); setBoardSnapshot(event.board.tokens); setChatTabs(event.chat_tabs); setSceneSnapshot(event.scenes, event.active_scene); setSceneLayers(event.scene_layers); setBgmSnapshot(event.bgm_tracks, event.bgm_playback); setChatNameInput(event.self.display_name); setChatTabId(event.chat_tabs.find((tab) => tab.tab_type === "main")?.tab_id ?? event.chat_tabs[0]?.tab_id ?? null); }
      if (event.type === "member.joined") addMember(event.member);
      if (event.type === "member.left") removeMember(event.user_id);
      if (event.type === "member.role.updated") updateMember(event.member);
      if (event.type === "member.removed") removeMember(event.user_id);
      if (event.type === "chat.message") addMessage(event.message);
      if (event.type === "dice.result") addMessage({ message_id: event.result.roll_id, user_id: event.result.user_id, display_name: event.result.display_name, text: `🎲 ${event.result.expression} = ${event.result.total}（${event.result.rolls.join(" + ")}${event.result.modifier ? ` ${event.result.modifier > 0 ? "+" : ""}${event.result.modifier}` : ""}）`, tab_id: event.result.tab_id });
      if (event.type === "scene.updated") updateScene(event.scene);
      if (event.type === "scene.activated") { activateScene(event.scene); setSceneLayers(event.layers); }
      if (event.type === "scene.layer.upserted") upsertSceneLayer(event.layer);
      if (event.type === "scene.layer.removed") removeSceneLayer(event.layer_id);
      if (event.type === "bgm.track.upserted") upsertBgmTrack(event.track);
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
      socketRef.current.send(JSON.stringify({ type: "scene.layer.upsert", scene_id: activeScene.scene_id, layer_type: layerTypeInput, name: layerNameInput.trim(), image_url: imageUrl, text: layerTextInput.trim(), x: 0.5, y: 0.5, width: 0.4, height: 0.3, z_index: layerTypeInput === "background" ? -10 : layerTypeInput === "foreground" ? 10 : 0, visible: true }));
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

  const handleFocusTool = (selector: string) => {
    document.querySelector(selector)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  };

  const handleAddBgm = async (event: FormEvent) => {
    event.preventDefault();
    if (self?.role !== "gm" || socketRef.current?.readyState !== WebSocket.OPEN || !bgmFile || !bgmNameInput.trim()) return;
    try {
      const audioUrl = await uploadAsset(bgmFile);
      socketRef.current.send(JSON.stringify({ type: "bgm.track.upsert", slot: bgmSlotInput, name: bgmNameInput.trim(), audio_url: audioUrl, loop: true }));
      setBgmNameInput("");
      setBgmFile(null);
    } catch (error) {
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
    const response = await fetch(`${apiBaseUrl}/api/rooms/${encodeURIComponent(roomId)}/assets`, {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}`, "Content-Type": file.type },
      body: file,
    });
    if (!response.ok) throw new Error("图片上传失败");
    const result = await response.json() as { url: string };
    return result.url.startsWith("http") ? result.url : `${apiBaseUrl}${result.url}`;
  };

  const handleSaveToken = async (event: FormEvent) => {
    event.preventDefault();
    const selectedToken = tokens.find((token) => token.token_id === selectedTokenId);
    if (!selectedToken || !self || (self.role !== "gm" && selectedToken.owner_user_id !== self.user_id) || socketRef.current?.readyState !== WebSocket.OPEN) return;
    try {
      const imageUrl = tokenImageFile ? await uploadAsset(tokenImageFile) : selectedToken.presentation?.image_url ?? null;
      socketRef.current.send(JSON.stringify({ type: "board.token.upsert", token_id: selectedToken.token_id, name: tokenNameInput.trim() || selectedToken.name, x: selectedToken.x, y: selectedToken.y, color: selectedToken.color }));
      socketRef.current.send(JSON.stringify({ type: "board.token.presentation.update", token_id: selectedToken.token_id, token_type: imageUrl ? "character" : "npc", image_url: imageUrl, scale: Number(tokenScaleInput) || 1, active_face_id: selectedToken.presentation?.active_face_id ?? null }));
      setTokenImageFile(null);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Token 保存失败");
    }
  };

  const handleAddFace = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedTokenId || !faceLabelInput.trim() || !faceImageFile || socketRef.current?.readyState !== WebSocket.OPEN) return;
    try {
      const imageUrl = await uploadAsset(faceImageFile);
      socketRef.current.send(JSON.stringify({ type: "board.token.face.upsert", token_id: selectedTokenId, label: faceLabelInput.trim(), image_url: imageUrl }));
      setFaceLabelInput("");
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
    socketRef.current.send(JSON.stringify({ type: "board.token.upsert", name: nameInput.trim() || "调查员", x: 0.5, y: 0.5, color: "#d7b56d" }));
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
  const stageMessage = [...visibleMessages].reverse().find((message) => message.show_dialogue && message.token_id);
  const stageToken = stageMessage ? tokens.find((token) => token.token_id === stageMessage.token_id) : undefined;
  const stageFace = stageToken?.faces?.find((face) => face.face_id === stageMessage?.face_id) ?? stageToken?.faces?.find((face) => face.face_id === stageToken.presentation?.active_face_id);
  const stageImage = stageFace?.image_url ?? stageToken?.presentation?.image_url;
  const ownTokens = tokens.filter((token) => token.owner_user_id === self?.user_id);
  const chatToken = ownTokens.find((token) => token.token_id === chatTokenId);
  const chatTokenFace = chatToken?.faces?.find((face) => face.face_id === chatToken.presentation?.active_face_id);
  const chatTokenImage = chatTokenFace?.image_url ?? chatToken?.presentation?.image_url;

  return (
    <main className="app-shell">
      <header className="topbar">
        <div><span className="eyebrow">COC-STAR / ROOM</span><h1>旧车站调查</h1></div>
        <div className="topbar-actions">{user && <span className="account-label">{user.username}</span>}<div className="connection-status"><span className={`status-dot status-${connectionStatus}`} />{connectionStatusLabel(connectionStatus)}</div>{user && <button type="button" className="logout-button" onClick={handleLogout}>退出</button>}</div>
      </header>
      <form className="auth-controls" onSubmit={handleAuthSubmit}>
        <span className="auth-title">{authMode === "login" ? "账号登录" : "创建账号"}</span>
        <input aria-label="账号" placeholder="账号" value={usernameInput} onChange={(event) => setUsernameInput(event.target.value)} minLength={3} maxLength={32} />
        <input aria-label="密码" placeholder="密码（至少 8 位）" type="password" value={passwordInput} onChange={(event) => setPasswordInput(event.target.value)} minLength={8} maxLength={128} />
        <button type="submit">{authMode === "login" ? "登录" : "注册"}</button>
        <button type="button" className="secondary-button" onClick={() => setAuthMode(authMode === "login" ? "register" : "login")}>{authMode === "login" ? "切换注册" : "已有账号"}</button>
      </form>
      <form className="room-controls" onSubmit={handleJoinRoom}>
        <label>房间号<input value={roomInput} onChange={(event) => setRoomInput(event.target.value)} /></label>
        <label>玩家名<input value={nameInput} onChange={(event) => setNameInput(event.target.value)} /></label>
        <button type="button" onClick={handleCreateRoom} disabled={!user}>创建房间</button>
        <button type="submit" disabled={!user}>{connectionStatus === "connecting" ? "连接中…" : "加入房间"}</button>
        {!user && <span className="error-message">请先登录后进入房间</span>}
        {errorMessage && <span className="error-message">{errorMessage}</span>}
      </form>
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
          <div className="board-toolbar"><span className="toolbar-title">{activeScene?.name ?? "未选择场景"}</span><div className="toolbar-actions"><button type="button" onClick={handleAddToken}>添加棋子</button>{scenes.map((scene) => <button type="button" key={scene.scene_id} className={scene.is_active ? "active-tool" : ""} onClick={() => handleActivateScene(scene.scene_id)}>{scene.name}</button>)}</div></div>
          {self?.role === "gm" && <form className="scene-form" onSubmit={handleCreateScene}><input aria-label="场景名称" placeholder="新场景名称" value={sceneNameInput} onChange={(event) => setSceneNameInput(event.target.value)} /><input aria-label="背景图地址" placeholder="背景图 URL（可选）" value={sceneBackgroundInput} onChange={(event) => setSceneBackgroundInput(event.target.value)} /><button type="submit">创建场景</button></form>}
          {self?.role === "gm" && <form className="scene-layer-form" onSubmit={handleAddLayer}><select aria-label="图层类型" value={layerTypeInput} onChange={(event) => setLayerTypeInput(event.target.value as SceneLayer["layer_type"])}><option value="background">背景</option><option value="foreground">前景</option><option value="panel">屏幕面板</option><option value="marker">标记</option></select><input aria-label="图层名称" placeholder="图层名称" value={layerNameInput} onChange={(event) => setLayerNameInput(event.target.value)} /><input aria-label="标记文字" placeholder="标记文字（可选）" value={layerTextInput} onChange={(event) => setLayerTextInput(event.target.value)} /><input aria-label="图层图片" type="file" accept="image/png,image/jpeg,image/webp,image/gif" onChange={(event) => setLayerImageFile(event.target.files?.[0] ?? null)} /><button type="submit">添加图层</button></form>}
          {sceneLayers.length > 0 && <div className="scene-layer-list">{sceneLayers.map((layer) => <div className="scene-layer-row" key={layer.layer_id}><span>{layer.name}</span><small>{layer.layer_type}</small>{self?.role === "gm" && <><button type="button" onClick={() => handleToggleLayer(layer)}>{layer.visible ? "隐藏" : "显示"}</button><button type="button" onClick={() => handleRemoveLayer(layer)}>删除</button></>}</div>)}</div>}
          <section className="bgm-panel"><div className="panel-heading"><span>BGM 播放</span><span className="muted">房间同步 / 本地音量</span></div>{self?.role === "gm" && <form className="bgm-upload-form" onSubmit={handleAddBgm}><select value={bgmSlotInput} onChange={(event) => setBgmSlotInput(event.target.value as BgmSlot)} aria-label="BGM 槽位"><option value="bgm01">BGM01</option><option value="bgm02">BGM02</option></select><input value={bgmNameInput} onChange={(event) => setBgmNameInput(event.target.value)} placeholder="曲目名称" aria-label="曲目名称" /><input type="file" accept="audio/mpeg,audio/ogg,audio/wav,audio/mp4" onChange={(event) => setBgmFile(event.target.files?.[0] ?? null)} aria-label="BGM 音频" /><button type="submit">上传到槽位</button></form>}<div className="bgm-list">{(["bgm01", "bgm02"] as BgmSlot[]).map((slot) => { const track = bgmTracks.find((item) => item.slot === slot); const playback = bgmPlayback.find((item) => item.slot === slot); return <div className="bgm-row" key={slot}><div className="bgm-info"><strong>{slot.toUpperCase()}</strong><span>{track?.name ?? "未设置曲目"}</span></div><div className="bgm-controls">{self?.role === "gm" && <><button type="button" disabled={!track} onClick={() => handleBgmControl(slot, "play")}>播放</button><button type="button" disabled={!track} onClick={() => handleBgmControl(slot, "pause")}>暂停</button><button type="button" disabled={!track} onClick={() => handleBgmControl(slot, "stop")}>停止</button>{track && <button type="button" onClick={() => socketRef.current?.send(JSON.stringify({ type: "bgm.track.remove", bgm_id: track.bgm_id }))}>移除</button>}</>}<input type="range" min="0" max="1" step="0.05" value={bgmVolume[slot]} onChange={(event) => handleBgmVolume(slot, Number(event.target.value))} aria-label={`${slot} 音量`} /><button type="button" onClick={() => handleBgmMute(slot)}>{bgmMuted[slot] ? "取消静音" : "静音"}</button><small>{playback?.is_playing ? "播放中" : "已暂停"}</small></div></div>; })}</div></section>
          {canEditSelectedToken && selectedToken && <TokenEditor token={selectedToken} tokenNameInput={tokenNameInput} tokenScaleInput={tokenScaleInput} faceLabelInput={faceLabelInput} onNameChange={setTokenNameInput} onScaleChange={setTokenScaleInput} onImageChange={setTokenImageFile} onSave={handleSaveToken} onFaceLabelChange={setFaceLabelInput} onFaceImageChange={setFaceImageFile} onAddFace={handleAddFace} onRemoveFace={handleRemoveFace} />}
          <div className="quick-tools"><button type="button" onClick={handleAddToken}>Token</button><button type="button" onClick={() => handleFocusTool(".scene-layer-form")}>图层</button><button type="button" onClick={() => handleFocusTool(".bgm-panel")}>音乐</button><button type="button" onClick={() => handleFocusTool(".chat-composer")}>发言</button></div>
          {self?.role === "gm" && sceneLayers.length > 0 && <div className="layer-nudge"><label>调整图层<select value={selectedLayerId ?? ""} onChange={(event) => setSelectedLayerId(event.target.value || null)}><option value="">选择图层</option>{sceneLayers.map((layer) => <option value={layer.layer_id} key={layer.layer_id}>{layer.name}</option>)}</select></label><div className="nudge-buttons"><button type="button" onClick={() => handleNudgeLayer(0, -0.02)}>上</button><button type="button" onClick={() => handleNudgeLayer(-0.02, 0)}>左</button><button type="button" onClick={() => handleNudgeLayer(0.02, 0)}>右</button><button type="button" onClick={() => handleNudgeLayer(0, 0.02)}>下</button></div><small>每次移动 2%</small></div>}
          {stageMessage && <div className="stage-dialogue"><div className="stage-portrait" style={stageImage ? { backgroundImage: `url(${stageImage})` } : { background: stageToken?.color ?? "#d7b56d" }}>{stageImage ? "" : (stageMessage.character_name || stageMessage.display_name).slice(0, 1)}</div><div className="stage-dialogue-body"><strong style={{ color: stageMessage.character_color ?? "#f0dca9" }}>{stageMessage.character_name || stageMessage.display_name}</strong><p>{stageMessage.text}</p></div></div>}
          <div className="board" ref={boardRef} style={activeScene?.background_url ? { backgroundImage: `linear-gradient(#10121866, #10121866), url(${activeScene.background_url})`, backgroundSize: "cover", backgroundPosition: "center" } : undefined}><div className="board-grid" />{sceneLayers.filter((layer) => layer.visible).map((layer) => <div className={`scene-layer scene-layer-${layer.layer_type}`} key={layer.layer_id} style={{ left: `${layer.x * 100}%`, top: `${layer.y * 100}%`, width: `${layer.width * 100}%`, height: `${layer.height * 100}%`, zIndex: layer.layer_type === "background" ? 0 : Math.max(layer.z_index, 2), backgroundImage: layer.image_url ? `url(${layer.image_url})` : undefined }}>{layer.text}</div>)}<div className="board-location">{activeScene?.name ?? "未选择场景"}</div>{tokens.map((token) => { const face = token.faces?.find((item) => item.face_id === token.presentation?.active_face_id); const imageUrl = face?.image_url ?? token.presentation?.image_url; return <button className={`token ${selectedTokenId === token.token_id ? "token-selected" : ""}`} key={token.token_id} draggable style={{ left: `${token.x * 100}%`, top: `${token.y * 100}%`, width: `${56 * (token.presentation?.scale ?? 1)}px`, height: `${56 * (token.presentation?.scale ?? 1)}px`, background: imageUrl ? `url(${imageUrl}) center / cover` : token.color }} onClick={() => setSelectedTokenId(token.token_id)} onDragEnd={(event) => handleMoveToken(token, event)} onDoubleClick={() => handleRemoveToken(token.token_id)} title="点击编辑，拖动移动，双击删除">{imageUrl ? "" : token.name.slice(0, 1)}</button>; })}{tokens.length === 0 && <div className="board-empty-state"><span className="empty-icon">✦</span><strong>虚拟桌面准备就绪</strong><p>点击“添加棋子”，创建第一个可同步角色</p></div>}</div>
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
          onTokenChange={setChatTokenId}
          selectedTokenImage={chatTokenImage}
          selectedTokenColor={chatToken?.color}
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
  selectedTokenImage?: string | null;
  selectedTokenColor?: string;
  chatName: string;
  onChatNameChange: (value: string) => void;
  chatColor: string;
  onChatColorChange: (value: string) => void;
  message: string;
  onMessageChange: (value: string) => void;
  onSend: (event: FormEvent) => void;
}

function ChatPanel({ collapsed, tabs, activeTabId, onToggleCollapsed, onTabChange, showChannelForm, onToggleChannelForm, channelName, onChannelNameChange, channelDialogue, onChannelDialogueChange, onCreateChannel, messages, ownTokens, selectedTokenId, onTokenChange, selectedTokenImage, selectedTokenColor, chatName, onChatNameChange, chatColor, onChatColorChange, message, onMessageChange, onSend }: ChatPanelProps) {
  return <aside className={`chat-panel ${collapsed ? "chat-panel-collapsed" : ""}`}>
    <div className="chat-panel-header"><span>聊天频道</span><button type="button" onClick={onToggleCollapsed}>{collapsed ? "展开" : "收起"}</button></div>
    {!collapsed && <>
      <div className="chat-tabs">{tabs.map((tab) => <button type="button" key={tab.tab_id} className={tab.tab_id === activeTabId ? "active-chat-tab" : ""} onClick={() => onTabChange(tab.tab_id)}>{tab.name}</button>)}<button type="button" className="chat-tab-add" onClick={onToggleChannelForm}>＋</button></div>
      {showChannelForm && <form className="channel-form" onSubmit={onCreateChannel}><input value={channelName} onChange={(event) => onChannelNameChange(event.target.value)} placeholder="频道名称" maxLength={40} /><label><input type="checkbox" checked={channelDialogue} onChange={(event) => onChannelDialogueChange(event.target.checked)} />开启立绘对话</label><button type="submit">添加</button></form>}
      <div className="message-list">{messages.map((item) => <MessageRow key={item.message_id} message={item} />)}{messages.length === 0 && <p className="empty-copy">当前频道还没有消息</p>}</div>
      <div className="chat-identity"><div className="chat-portrait" style={selectedTokenImage ? { backgroundImage: `url(${selectedTokenImage})` } : { background: selectedTokenColor ?? "#3a4050" }}>{selectedTokenImage ? "" : "无"}</div><select aria-label="选择角色卡" value={selectedTokenId ?? ""} onChange={(event) => onTokenChange(event.target.value || null)}><option value="">☰ 无（不使用角色卡）</option>{ownTokens.map((token) => <option value={token.token_id} key={token.token_id}>☰ {token.name}</option>)}</select><input aria-label="发言名称" value={chatName} onChange={(event) => onChatNameChange(event.target.value)} maxLength={40} /><input className="chat-color-picker" aria-label="名字颜色" type="color" value={chatColor} onChange={(event) => onChatColorChange(event.target.value)} /></div>
      <div className="dice-shortcuts">{["1d100", "1d20", "1d6", "2d6+3"].map((expression) => <button type="button" key={expression} onClick={() => onMessageChange(`/r ${expression}`)}>◇ {expression}</button>)}</div>
      <form className="chat-composer" onSubmit={onSend}><input aria-label="聊天消息" placeholder="输入消息…" value={message} onChange={(event) => onMessageChange(event.target.value)} /><button type="submit">发送</button></form>
    </>}
  </aside>;
}

function connectionStatusLabel(status: string) {
  return { disconnected: "未连接", connecting: "连接中", connected: "已连接", error: "连接异常" }[status] ?? status;
}

interface TokenEditorProps {
  faceLabelInput: string;
  onAddFace: (event: FormEvent) => void;
  onFaceImageChange: (file: File | null) => void;
  onFaceLabelChange: (value: string) => void;
  onImageChange: (file: File | null) => void;
  onNameChange: (value: string) => void;
  onRemoveFace: (face: TokenFace) => void;
  onSave: (event: FormEvent) => void;
  onScaleChange: (value: string) => void;
  token: BoardToken;
  tokenNameInput: string;
  tokenScaleInput: string;
}

function TokenEditor({ faceLabelInput, onAddFace, onFaceImageChange, onFaceLabelChange, onImageChange, onNameChange, onRemoveFace, onSave, onScaleChange, token, tokenNameInput, tokenScaleInput }: TokenEditorProps) {
  return <section className="token-editor"><div className="token-editor-heading"><strong>Token 编辑</strong><span>{token.presentation?.image_url ? "角色" : "NPC"}</span></div><form className="token-editor-form" onSubmit={onSave}><label>名称<input value={tokenNameInput} onChange={(event) => onNameChange(event.target.value)} maxLength={40} /></label><label>大小<input type="number" min="0.25" max="4" step="0.25" value={tokenScaleInput} onChange={(event) => onScaleChange(event.target.value)} /></label><label>立绘<input type="file" accept="image/png,image/jpeg,image/webp,image/gif" onChange={(event) => onImageChange(event.target.files?.[0] ?? null)} /></label><button type="submit">保存 Token</button></form><div className="face-editor"><span className="face-editor-title">自定义差分</span><form onSubmit={onAddFace}><input aria-label="差分关键词" placeholder="关键词，如：哭泣" value={faceLabelInput} onChange={(event) => onFaceLabelChange(event.target.value)} maxLength={80} /><input aria-label="差分图片" type="file" accept="image/png,image/jpeg,image/webp,image/gif" onChange={(event) => onFaceImageChange(event.target.files?.[0] ?? null)} /><button type="submit">添加差分</button></form><div className="face-list">{(token.faces ?? []).map((face) => <div className="face-row" key={face.face_id}><img src={face.image_url} alt={face.label} /><span>#{face.label}</span><button type="button" onClick={() => onRemoveFace(face)}>删除</button></div>)}{(token.faces ?? []).length === 0 && <small>还没有差分，添加后可在发言末尾使用 #关键词 切换。</small>}</div></div></section>;
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
