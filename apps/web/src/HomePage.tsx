import type { FormEvent } from "react";

import type { AccountUser } from "./authStore";
import type { ConnectionStatus } from "./roomStore";

export interface HomePageProps {
  connectionStatus: ConnectionStatus;
  displayName: string;
  errorMessage: string | null;
  isLoadingRooms: boolean;
  roomId: string;
  rooms: RoomSummary[];
  user: AccountUser;
  onCreateRoom: () => void;
  onDisplayNameChange: (value: string) => void;
  onJoinRoom: (event: FormEvent) => void;
  onLogout: () => void;
  onOpenRoom: (roomId: string) => void;
  onOpenKnowledgeBase: (kind: "knowledge" | "documents") => void;
  onRemoveRoom: (room: RoomSummary) => void;
  onRoomIdChange: (value: string) => void;
  onRefreshRooms: () => void;
}

export interface RoomSummary {
  created_at: string | null;
  display_name: string;
  is_owner: boolean;
  name: string;
  role: string;
  room_id: string;
}

export function HomePage({ connectionStatus, displayName, errorMessage, isLoadingRooms, roomId, rooms, user, onCreateRoom, onDisplayNameChange, onJoinRoom, onLogout, onOpenRoom, onOpenKnowledgeBase, onRemoveRoom, onRoomIdChange, onRefreshRooms }: HomePageProps) {
  const ownedRooms = rooms.filter((room) => room.is_owner);
  const joinedRooms = rooms.filter((room) => !room.is_owner);

  return <main className="home-page">
    <header className="home-header"><span className="brand-mark">COC-STAR</span><div><span className="account-chip">{user.username}</span><button className="text-action" type="button" onClick={onLogout}>退出</button></div></header>
    <section className="home-hero"><div className="home-hero-copy"><span className="eyebrow">房间大厅</span><h1>下一幕，从这里开始。</h1><p>创建自己的跑团房间，或使用房间号加入同伴正在进行的故事。</p></div><div className="home-overview"><span className="home-overview-label">当前空间</span><strong>{rooms.length}</strong><small>个房间</small><div className="home-overview-line"><span>创建 {ownedRooms.length}</span><span>加入 {joinedRooms.length}</span></div></div></section>
    <section className="room-entry-grid">
      <article className="room-entry-card room-entry-primary"><span className="eyebrow">新建</span><h2>创建一间房</h2><p>你会成为 GM，并获得场景、图层与音乐控制权。</p><label>显示名称<input value={displayName} onChange={(event) => onDisplayNameChange(event.target.value)} maxLength={40} required /></label><button className="primary-action" type="button" onClick={onCreateRoom} disabled={!displayName.trim() || connectionStatus === "connecting"}>创建并进入</button></article>
      <article className="room-entry-card"><span className="eyebrow">加入</span><h2>进入已有房间</h2><p>输入房间号后，以玩家身份加入当前的跑团。</p><form className="join-room-form" onSubmit={onJoinRoom}><label>房间号<input value={roomId} onChange={(event) => onRoomIdChange(event.target.value)} required /></label><label>显示名称<input value={displayName} onChange={(event) => onDisplayNameChange(event.target.value)} maxLength={40} required /></label><button className="secondary-action" type="submit" disabled={!displayName.trim() || !roomId.trim() || connectionStatus === "connecting"}>{connectionStatus === "connecting" ? "正在连接" : "加入房间"}</button></form></article>
    </section>
    <section className="home-section knowledge-section"><div className="section-heading"><div><span className="eyebrow">准备工作</span><h2>知识库</h2></div><span>为后续 AI 辅助跑团预留</span></div><div className="knowledge-grid"><button type="button" className="knowledge-card" onClick={() => onOpenKnowledgeBase("knowledge")}><span className="knowledge-icon">✦</span><strong>知识库</strong><small>整理世界观、规则与设定</small><em>进入管理</em></button><button type="button" className="knowledge-card" onClick={() => onOpenKnowledgeBase("documents")}><span className="knowledge-icon">▤</span><strong>文档库</strong><small>集中保存剧本、手册与资料</small><em>进入管理</em></button></div></section>
    <section className="home-section rooms-section"><div className="section-heading"><div><span className="eyebrow">你的空间</span><h2>我的房间</h2></div><button type="button" className="text-action" onClick={onRefreshRooms}>{isLoadingRooms ? "读取中…" : "刷新"}</button></div><div className="room-columns"><RoomList title="我创建的" rooms={ownedRooms} emptyText="还没有创建房间" onOpenRoom={onOpenRoom} onRemoveRoom={onRemoveRoom} /><RoomList title="我加入的" rooms={joinedRooms} emptyText="还没有加入其他房间" onOpenRoom={onOpenRoom} onRemoveRoom={onRemoveRoom} /></div></section>
    {errorMessage && <p className="home-error" role="alert">{errorMessage}</p>}
    <p className="home-note">知识库与房间列表现在已预留独立入口；知识库内容和创建房间时绑定知识库会在 AI 功能阶段接入。</p>
  </main>;
}

function RoomList({ emptyText, onOpenRoom, onRemoveRoom, rooms, title }: { emptyText: string; onOpenRoom: (roomId: string) => void; onRemoveRoom: (room: RoomSummary) => void; rooms: RoomSummary[]; title: string }) {
  return <div className="room-list-card"><div className="room-list-heading"><strong>{title}</strong><span>{rooms.length}</span></div>{rooms.length === 0 ? <p className="room-list-empty">{emptyText}</p> : rooms.map((room) => <div className="room-list-item" key={room.room_id}><button type="button" className="room-list-enter" onClick={() => onOpenRoom(room.room_id)}><span className="room-list-main"><strong>{room.name}</strong><small>{room.room_id}</small></span><span className="room-list-meta">{room.role === "gm" ? "GM" : "玩家"}<b>进入 →</b></span></button><button type="button" className="room-list-remove" onClick={() => onRemoveRoom(room)}>{room.is_owner ? "删除" : "退出"}</button></div>)}</div>;
}
