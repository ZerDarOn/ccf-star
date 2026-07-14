import type { FormEvent } from "react";

export interface DiceShortcut {
  id: string;
  label: string;
  expression: string;
}

interface DiceConfigPanelProps {
  shortcuts: DiceShortcut[];
  onChange: (shortcuts: DiceShortcut[]) => void;
}

export function DiceConfigPanel({ shortcuts, onChange }: DiceConfigPanelProps) {
  const handleChange = (id: string, field: "label" | "expression", value: string) => {
    onChange(shortcuts.map((shortcut) => shortcut.id === id ? { ...shortcut, [field]: value } : shortcut));
  };
  const handleAdd = (event: FormEvent) => {
    event.preventDefault();
    onChange([...shortcuts, { id: `shortcut-${Date.now()}`, label: "新骰子", expression: "1d100" }]);
  };
  return <section className="dice-config-panel">
    <div className="drawer-section-heading"><span>规则系统</span><small>当前使用 COC 第七版</small></div>
    <p className="drawer-hint">普通骰子使用 NdM、NdM+K 格式，例如 1d100、2d6+3。COC 检定可以输入 {"{侦查}"} 或 cc&lt;=70。</p>
    <div className="dice-config-system"><strong>COC 7th</strong><span>百分骰检定 · 极难 / 困难 / 成功 / 失败 / 大失败</span></div>
    <div className="drawer-section-heading"><span>我的快捷骰子</span><button type="button" onClick={handleAdd}>添加</button></div>
    <div className="dice-config-list">{shortcuts.map((shortcut) => <div className="dice-config-row" key={shortcut.id}>
      <input aria-label={`${shortcut.label} 名称`} value={shortcut.label} onChange={(event) => handleChange(shortcut.id, "label", event.target.value)} maxLength={20} />
      <input aria-label={`${shortcut.label} 表达式`} value={shortcut.expression} onChange={(event) => handleChange(shortcut.id, "expression", event.target.value)} maxLength={32} />
      <button type="button" className="dice-config-remove" onClick={() => onChange(shortcuts.filter((item) => item.id !== shortcut.id))}>删除</button>
    </div>)}</div>
    <button type="button" className="dice-config-reset" onClick={() => onChange([
      { id: "d100", label: "百分骰", expression: "1d100" },
      { id: "d20", label: "D20", expression: "1d20" },
      { id: "d6", label: "D6", expression: "1d6" },
      { id: "damage", label: "伤害", expression: "2d6+3" },
    ])}>恢复默认快捷骰子</button>
  </section>;
}
