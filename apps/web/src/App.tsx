import { useEffect, useRef, useState } from "react";
import type { DragEvent, FormEvent } from "react";
import { AccountUser, useAuthStore } from "./authStore";
import { BoardToken, ChatMessage, RoomMember, useRoomStore } from "./roomStore";

type RoomEvent =
  | { type: "room.connected"; room_id: string; self: RoomMember; members: RoomMember[]; board: { tokens: BoardToken[] } }
  | { type: "member.joined"; member: RoomMember }
  | { type: "member.left"; user_id: string }
  | { type: "member.role.updated"; member: RoomMember }
  | { type: "member.removed"; user_id: string }
  | { type: "chat.message"; message: ChatMessage }
  | { type: "board.token.upserted"; token: BoardToken }
  | { type: "board.token.removed"; token_id: string }
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

export function App() {
  const socketRef = useRef<WebSocket | null>(null);
  const boardRef = useRef<HTMLDivElement | null>(null);
  const [roomInput, setRoomInput] = useState("demo-room");
  const [nameInput, setNameInput] = useState("苏鸣澈");
  const [messageInput, setMessageInput] = useState("");
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [usernameInput, setUsernameInput] = useState("");
  const [passwordInput, setPasswordInput] = useState("");
  const { accessToken, refreshToken, user, setSession, clearSession } = useAuthStore();
  const { connectionStatus, errorMessage, members, messages, self, roomId, tokens, setConnectionStatus, setRoomSnapshot, setBoardSnapshot, addMember, updateMember, removeMember, addMessage, upsertToken, removeToken, setErrorMessage } = useRoomStore();

  useEffect(() => () => socketRef.current?.close(), []);

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
      if (event.type === "room.connected") { setConnectionStatus("connected"); setRoomSnapshot(event.room_id, event.self, event.members); setBoardSnapshot(event.board.tokens); }
      if (event.type === "member.joined") addMember(event.member);
      if (event.type === "member.left") removeMember(event.user_id);
      if (event.type === "member.role.updated") updateMember(event.member);
      if (event.type === "member.removed") removeMember(event.user_id);
      if (event.type === "chat.message") addMessage(event.message);
      if (event.type === "board.token.upserted") upsertToken(event.token);
      if (event.type === "board.token.removed") removeToken(event.token_id);
      if (event.type === "error") setErrorMessage(`房间服务错误：${event.code}`);
    } catch {
      setErrorMessage("收到无法识别的房间事件");
    }
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
    socketRef.current.send(JSON.stringify({ type: "chat.message", text }));
    setMessageInput("");
  };

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
      <section className="workspace">
        <aside className="sidebar">
          <div className="panel-heading"><span>房间成员</span><span className="muted">{members.length} / 8</span></div>
          <div className="player-list">
            {members.map((member) => <MemberRow key={member.user_id} member={member} self={member.user_id === self?.user_id} canManage={self?.role === "gm"} onRoleUpdate={handleMemberRoleUpdate} onRemove={handleMemberRemove} />)}
            {members.length === 0 && <p className="empty-copy">加入房间后会显示在线成员</p>}
          </div>
          <div className="sidebar-note"><span>当前房间</span><p>{roomId}</p></div>
        </aside>
        <section className="board-area">
          <div className="board-toolbar"><span className="toolbar-title">场景 01 · 旧车站月台</span><div className="toolbar-actions"><button type="button" onClick={handleAddToken}>添加棋子</button><button type="button">场景</button><button type="button">资源</button></div></div>
          <div className="board" ref={boardRef}><div className="board-grid" /><div className="board-location">旧车站 · 23:48</div>{tokens.map((token) => <button className="token" key={token.token_id} draggable style={{ left: `${token.x * 100}%`, top: `${token.y * 100}%`, background: token.color }} onDragEnd={(event) => handleMoveToken(token, event)} onDoubleClick={() => handleRemoveToken(token.token_id)} title="拖动移动，双击删除">{token.name.slice(0, 1)}</button>)}{tokens.length === 0 && <div className="board-empty-state"><span className="empty-icon">✦</span><strong>虚拟桌面准备就绪</strong><p>点击“添加棋子”，创建第一个可同步角色</p></div>}</div>
        </section>
        <aside className="chat-panel">
          <div className="panel-heading"><span>主频道</span><span className="muted">{messages.length} 条消息</span></div>
          <div className="message-list">{messages.map((message) => <MessageRow key={message.message_id} message={message} />)}{messages.length === 0 && <p className="empty-copy">还没有消息，先打个招呼吧</p>}</div>
          <form className="chat-composer" onSubmit={handleSendMessage}><span>{self?.display_name ?? nameInput}</span><input aria-label="聊天消息" placeholder="输入消息……" value={messageInput} onChange={(event) => setMessageInput(event.target.value)} /><button type="submit">发送</button></form>
        </aside>
      </section>
    </main>
  );
}

function connectionStatusLabel(status: string) {
  return { disconnected: "未连接", connecting: "连接中", connected: "已连接", error: "连接异常" }[status] ?? status;
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
  return <article className="message"><div className="message-meta"><strong>{message.display_name}</strong><time>刚刚</time></div><p>{message.text}</p></article>;
}

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(Math.max(value, minimum), maximum);
}
