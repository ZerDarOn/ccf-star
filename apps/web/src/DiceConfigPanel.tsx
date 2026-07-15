import { useState } from "react";
import type { FormEvent } from "react";

export interface DiceShortcut {
  id: string;
  label: string;
  expression: string;
}

interface DiceConfigPanelProps {
  shortcuts: DiceShortcut[];
  onChange: (shortcuts: DiceShortcut[]) => void;
  onRunCheck: (target: string, mode: "normal" | "bonus" | "penalty") => void;
  characterSkills?: Record<string, number> | null;
}

const cocEvents = [
  ["accounting", "会计"], ["anthropology", "人类学"], ["appraise", "估价"], ["archaeology", "考古学"],
  ["charm", "取悦"], ["climb", "攀爬"], ["computer_use", "计算机使用"], ["credit_rating", "信用评级"],
  ["cthulhu_mythos", "克苏鲁神话"], ["disguise", "乔装"], ["dodge", "闪避"], ["drive_auto", "汽车驾驶"],
  ["elec_repair", "电气维修"], ["electronics", "电子学"], ["fast_talk", "话术"], ["fighting", "斗殴"],
  ["firearms_handgun", "手枪"], ["first_aid", "急救"], ["history", "历史"], ["intimidate", "恐吓"],
  ["jump", "跳跃"], ["language_own", "母语"], ["law", "法律"], ["library_use", "图书馆使用"],
  ["listen", "聆听"], ["locksmith", "开锁"], ["mech_repair", "机械维修"], ["medicine", "医学"],
  ["natural_world", "博物学"], ["navigate", "领航"], ["occult", "神秘学"], ["operate_heavy_machinery", "重型操作"],
  ["persuade", "说服"], ["psychoanalysis", "精神分析"], ["psychology", "心理学"], ["ride", "骑术"],
  ["sleight_of_hand", "妙手"], ["spot_hidden", "侦查"], ["stealth", "潜行"], ["survival", "生存"],
  ["swim", "游泳"], ["throw", "投掷"], ["track", "追踪"], ["animal_handling", "驯兽"],
  ["diving", "潜水"], ["demolitions", "爆破"], ["lip_reading", "读唇"], ["hypnosis", "催眠"], ["artillery", "炮术"],
] as const;

const modeLabels = [
  ["normal", "普通"],
  ["bonus", "奖励"],
  ["penalty", "惩罚"],
] as const;

export function DiceConfigPanel({ shortcuts, onChange, onRunCheck, characterSkills }: DiceConfigPanelProps) {
  const [eventsOpen, setEventsOpen] = useState(false);
  const skillValue = (skillId: string) => characterSkills
    ? (characterSkills[skillId] !== undefined ? characterSkills[skillId] : "默认")
    : "未绑定角色卡";
  const handleChange = (id: string, field: "label" | "expression", value: string) => {
    onChange(shortcuts.map((shortcut) => shortcut.id === id ? { ...shortcut, [field]: value } : shortcut));
  };

  const handleAdd = (event: FormEvent) => {
    event.preventDefault();
    onChange([...shortcuts, { id: `shortcut-${Date.now()}`, label: "新骰子", expression: "1d100" }]);
  };

  return <section className="dice-config-panel">
    <div className="drawer-section-heading"><span>规则系统</span><small>当前使用 COC 第七版</small></div>
    <p className="drawer-hint">普通骰子使用 NdM、NdM+K 格式，例如 1d100、2d6+3。COC 检定也可以输入 {'{侦查}'} 或 cc&lt;=70。</p>
    <div className="dice-config-system"><strong>COC 7th</strong><span>百分骰检定 · 极难 / 困难 / 成功 / 失败 / 大失败</span></div>

    <button type="button" className="drawer-section-heading drawer-section-toggle" aria-expanded={eventsOpen} onClick={() => setEventsOpen((open) => !open)}><span>COC 判定事件</span><small>{eventsOpen ? "收起" : "点击展开技能目录"}　{eventsOpen ? "⌃" : "⌄"}</small></button>
    {eventsOpen && <div className="coc-event-list">
      {cocEvents.map(([skillId, label]) => <div className="coc-event-row" key={skillId}>
        <strong>{label}<small> {skillValue(skillId)}</small></strong>
        <div>
          {modeLabels.map(([mode, modeLabel]) => <button type="button" key={mode} onClick={() => onRunCheck(label, mode)}>{modeLabel}</button>)}
        </div>
      </div>)}
      {characterSkills && Object.keys(characterSkills).filter((skillId) => !cocEvents.some(([knownId]) => knownId === skillId)).map((skillId) => <div className="coc-event-row" key={skillId}><strong>{skillId}<small> {skillValue(skillId)}</small></strong><div>{modeLabels.map(([mode, modeLabel]) => <button type="button" key={mode} onClick={() => onRunCheck(skillId, mode)}>{modeLabel}</button>)}</div></div>)}
    </div>}

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
