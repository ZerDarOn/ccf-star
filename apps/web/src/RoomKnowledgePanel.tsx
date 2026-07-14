import type { KnowledgeBaseSummary } from "./RoomAiPanel";

interface RoomKnowledgePanelProps { bases: KnowledgeBaseSummary[]; mountedIds: string[]; onMountedIdsChange: (ids: string[]) => void; onSave: () => void; }

export function RoomKnowledgePanel({ bases, mountedIds, onMountedIdsChange, onSave }: RoomKnowledgePanelProps) {
  const toggleBase = (baseId: string, checked: boolean) => onMountedIdsChange(checked ? [...mountedIds, baseId] : mountedIds.filter((id) => id !== baseId));
  return <section className="room-knowledge-panel"><div className="drawer-hint">这里负责把首页维护好的知识库挂载到当前房间。AI 只会读取已挂载且文档允许参与 AI 的内容。</div><div className="room-knowledge-list">{bases.map((base) => <label className="room-knowledge-item" key={base.knowledge_base_id}><input type="checkbox" checked={mountedIds.includes(base.knowledge_base_id)} onChange={(event) => toggleBase(base.knowledge_base_id, event.target.checked)} /><span><strong>{base.name}</strong><small>{base.kind === "knowledge" ? "知识库" : "文档库"} · {base.document_count} 篇{base.parent_id ? " · 子分类" : ""}</small></span></label>)}{bases.length === 0 && <p className="drawer-hint">首页还没有可挂载的知识库。</p>}</div><button type="button" className="primary-action" onClick={onSave}>保存房间挂载</button></section>;
}
