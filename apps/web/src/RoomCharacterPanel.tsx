import type { CharacterSummary } from "./CharacterLibraryPanel";

export interface RoomCharacterSummary { room_character_id: string; character_id: string; sheet_data: Record<string, unknown>; active: boolean; }
interface RoomCharacterPanelProps { characters: CharacterSummary[]; roomCharacters: RoomCharacterSummary[]; onLoad: (characterId: string) => void; }

export function RoomCharacterPanel({ characters, roomCharacters, onLoad }: RoomCharacterPanelProps) {
  const loadedIds = new Set(roomCharacters.map((character) => character.character_id));
  return <div className="drawer-token-list"><div className="drawer-section-heading"><span>角色库</span><small>选择一张卡加载到本房间</small></div>{characters.map((character) => <div className="room-character-row" key={character.character_id}><div><strong>{character.name}</strong><small>{character.system.toUpperCase()} · {loadedIds.has(character.character_id) ? "已加载" : "未加载"}</small></div><button type="button" disabled={loadedIds.has(character.character_id)} onClick={() => onLoad(character.character_id)}>{loadedIds.has(character.character_id) ? "已使用" : "加载"}</button></div>)}{characters.length === 0 && <p className="empty-copy">首页角色库还没有角色卡。</p>}<div className="drawer-section-heading"><span>本房间角色</span><small>{roomCharacters.length} 张</small></div>{roomCharacters.map((character) => <div className="room-character-row" key={character.room_character_id}><strong>{characters.find((item) => item.character_id === character.character_id)?.name ?? "角色卡"}</strong><small>本房间副本 · HP / SAN 等状态独立保存</small></div>)}</div>;
}
